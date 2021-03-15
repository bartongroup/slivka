import logging
import threading
from collections import defaultdict, namedtuple, OrderedDict
from functools import partial
from importlib import import_module
from typing import (Iterable, Tuple, Dict, List, Any, Type, Union, DefaultDict,
                    Sequence)

from pymongo import UpdateOne

import slivka.db
from slivka.db.documents import (JobRequest, JobMetadata, CancelRequest,
                                 ServiceState)
from slivka.db.helpers import insert_many, replace_one
from slivka.scheduler.runners.runner import RunnerID, Runner
from slivka.utils import JobStatus, BackoffCounter


def _fetch_pending_requests(database) -> Iterable[JobRequest]:
    requests = (JobRequest
                .collection(database)
                .find({'status': JobStatus.PENDING}))
    return (JobRequest(**kwargs) for kwargs in requests)


def _fetch_cancel_requests(database) -> List[str]:
    requests = CancelRequest.collection(database).find()
    return [kwargs['uuid'] for kwargs in requests]


def get_classpath(cls):
    return cls.__module__ + '.' + cls.__name__


RunResult = namedtuple('RunResult', 'started, deferred, failed')

# sentinel valued corresponding to the rejected and error requests
REJECTED = object()
ERROR = object()


class Scheduler:
    """
    Scheduler is a central hub of the slivka system. It runs in it's
    individual process and manages jobs.

    In it's main loot, it first
    fetches the pending job requests from the database and sorts them
    to available runners using provided limiters (see :py:class:`Limiter`)
    for decision making. Then, the accepted requests are being executed
    with the runner and the created jobs are stored in the database.

    In the next stage, the scheduler checks all currently running jobs
    and updates their state into the database.
    """

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self._finished = threading.Event()
        self.runners = {}  # type: Dict[RunnerID, Runner]
        self.limiters = defaultdict(DefaultLimiter)  # type: Dict[str, Limiter]
        self._backoff_counters = defaultdict(
            partial(BackoffCounter, max_tries=10)
        )  # type: DefaultDict[Any, BackoffCounter]

    def is_running(self):
        """ Checks whether the scheduler is running. """
        return not self._finished.is_set()

    is_running = property(is_running)

    def set_failure_limit(self, limit):
        """ Sets the limit of allowed exceptions before job is rejected. """
        factory = partial(BackoffCounter, max_tries=limit)
        self._backoff_counters.default_factory = factory
        for counter in self._backoff_counters.values():
            counter.max_tries = limit

    def add_runner(self, runner: Runner):
        self.runners[runner.id] = runner

    def load_runners(self, service_name, conf_dict):
        """ Automatically adds runners from the configuration. """
        limiter_cp = conf_dict.get('limiter')
        if limiter_cp is not None:
            mod, attr = limiter_cp.rsplit('.', 1)
            self.limiters[service_name] = getattr(import_module(mod), attr)()
        for name, conf in conf_dict['runners'].items():
            if '.' in conf['class']:
                mod, attr = conf['class'].rsplit('.', 1)
            else:
                mod, attr = 'slivka.scheduler.runners', conf['class']
            cls = getattr(import_module(mod), attr)
            kwargs = conf.get('parameters', {})
            runner_id = RunnerID(service_name, name)
            runner = self.runners[runner_id] = cls(
                conf_dict, id=RunnerID(service_name, name), **kwargs
            )
            self.log.info('loaded runner for service %s: %r', service_name,
                          runner)

    def test_runners(self):
        """ Run tests for all runners. """
        for _id, runner in sorted(self.runners.items()):
            runner.run_test()

    def stop(self):
        self._finished.set()

    def run_forever(self):
        """ Starts the main loop

        The main loop is running until the :py:meth:`stop` is called.
        It repeatedly performs work cycles with one second delay
        between them.
        """
        if self._finished.is_set():
            raise RuntimeError
        self.reset_service_states()
        self.log.info('scheduler started')
        try:
            while not self._finished.wait(1):
                self.run_cycle()
        except KeyboardInterrupt:
            self.stop()

    def reset_service_states(self):
        """ Resets all service states in the database. """
        for service, runner in self.runners.keys():
            state = ServiceState(service=service, runner=runner)
            replace_one(
                slivka.db.database, state,
                filter_keys=['service', 'runner'], upsert=True
            )

    def run_cycle(self):
        log = self.log
        database = slivka.db.database

        # fetching new requests
        new_requests = _fetch_pending_requests(database)
        grouped = self.group_requests(new_requests)
        rejected = grouped.pop(REJECTED, ())
        if rejected:
            JobRequest.collection(database).update_many(
                {'_id': {'$in': [req.id for req in rejected]}},
                {'$set': {'status': JobStatus.REJECTED}}
            )
        error = grouped.pop(ERROR, ())
        if error:
            JobRequest.collection(database).update_many(
                {'_id': {'$in': [req.id for req in error]}},
                {'$set': {'status': JobStatus.ERROR}}
            )
        for runner, requests in grouped.items():
            JobRequest.collection(database).update_many(
                {'_id': {'$in': [req.id for req in requests]}},
                {'$set': {
                    'status': JobStatus.ACCEPTED,
                    'runner': runner.name
                }}
            )

        # Fetch cancel requests and update cancelled job states to
        # DELETED if they were PENDING or ACCEPTED; or CANCELLING if QUEUED or RUNNING
        cancel_requests = _fetch_cancel_requests(database)
        if cancel_requests:
            JobRequest.collection(database).update_many(
                {'uuid': {'$in': cancel_requests},
                 'status': {'$in': [JobStatus.PENDING, JobStatus.ACCEPTED]}},
                {'$set': {'status': JobStatus.DELETED}}
            )
            JobRequest.collection(database).update_many(
                {'uuid': {'$in': cancel_requests},
                 'status': {'$in': [JobStatus.QUEUED, JobStatus.RUNNING]}},
                {'$set': {'status': JobStatus.CANCELLING}}
            )
            cancelled_jobs = JobMetadata.find(
                database, {'uuid': {'$in': cancel_requests}})
            for job in cancelled_jobs:
                runner = self.runners[job.service, job.runner]
                runner.cancel(job.job_id, job.cwd)
            CancelRequest.collection(database).delete_many(
                {'uuid': {'$in': cancel_requests}})

        # starting ACCEPTED requests
        cursor = JobRequest.collection(database).aggregate([
            {'$match': {'status': JobStatus.ACCEPTED}},
            {'$group': {
                '_id': {'service_name': '$service',
                        'runner_name': '$runner'},
                'requests': {'$push': '$$CURRENT'}
            }}
        ])
        for item in cursor:
            requests = [JobRequest(**kw) for kw in item['requests']]
            try:
                runner = self.runners[RunnerID(**item['_id'])]
            except KeyError:
                log.exception("Runner not found")
                failed = requests
            else:
                started, deferred, failed = self.run_requests(runner, requests)
                new_jobs = []
                queued = []
                for request, job in started:
                    queued.append(request)
                    new_jobs.append(JobMetadata(
                        uuid=request.uuid,
                        service=request.service,
                        runner=runner.name,
                        runner_class=get_classpath(type(runner)),
                        job_id=job.id,
                        work_dir=job.cwd,
                        status=JobStatus.QUEUED
                    ))
                if new_jobs:
                    insert_many(database, new_jobs)
                    JobRequest.collection(database).update_many(
                        {'_id': {'$in': [req.id for req in queued]}},
                        {'$set': {'status': JobStatus.QUEUED}}
                    )
            if failed:
                JobRequest.collection(database).update_many(
                    {'_id': {'$in': [req.id for req in failed]}},
                    {'$set': {'status': JobStatus.ERROR}}
                )

        # monitoring jobs
        cursor = JobMetadata.collection(database).aggregate([
            {'$match': {
                'status': {'$in': (JobStatus.QUEUED, JobStatus.RUNNING)}}},
            {'$group': {
                '_id': '$runner_class',
                'jobs': {'$push': '$$CURRENT'}
            }}
        ])
        for item in cursor:
            jobs = [JobMetadata(**kw) for kw in item['jobs']]
            try:
                mod, attr = item['_id'].rsplit('.', 1)
                runner = getattr(import_module(mod), attr)
            except AttributeError:
                log.exception("Runner class cannot be imported")
                updated = [(job, JobStatus.ERROR) for job in jobs]
            else:
                updated = self.monitor_jobs(runner, jobs)
            if not updated:
                continue
            JobRequest.collection(database).bulk_write([
                UpdateOne({'uuid': job.uuid}, {'$set': {'status': state}})
                for (job, state) in updated
            ], ordered=False)
            JobMetadata.collection(database).bulk_write([
                UpdateOne({'_id': job.id}, {'$set': {'status': state}})
                for (job, state) in updated
            ], ordered=False)

    def group_requests(
            self, requests: Iterable[JobRequest]
    ) -> Dict[Union[Runner, object], List[JobRequest]]:
        """Group requests to their corresponding runners or reject."""
        grouped = defaultdict(list)
        for request in requests:
            limiter = self.limiters[request.service]
            runner_name = limiter(request.inputs)
            if runner_name is None:
                grouped[REJECTED].append(request)
            else:
                runner = self.runners[request.service, runner_name]
                grouped[runner].append(request)
        return grouped

    def run_requests(self, runner: Runner, requests: List[JobRequest]) \
            -> RunResult:
        """ Run all requests with the runner provided.

        Runs all the job requests using the supplied implementation
        of :py:class:`Runner` and returns a three-element tuple
        containing three groups of requests: started, deferred and failed.
        The "started" group contains an iterable of :py:class:`JobRequest`
        and :py:class:`RunInfo` pairs corresponding to the successfully
        started jobs. The "deferred" group contains requests delayed due
        to failure. The "failed" group contains requests that failed
        multiple run attempts and should not be repeated.
        """
        # FIXME: this method should have cleaner implementation
        counter = self._backoff_counters[runner]
        if not requests or next(counter) > 0:
            return RunResult(started=(), deferred=requests, failed=())
        try:
            jobs = runner.batch_run([req.inputs for req in requests])
            service_state = ServiceState(
                service=runner.service_name, runner=runner.name,
                state=ServiceState.State.OK)
            replace_one(slivka.db.database, service_state,
                        filter_keys=['service', 'runner'])
            return RunResult(
                started=zip(requests, jobs), deferred=(), failed=()
            )
        except Exception as exc:
            self.log.exception("Running %s requests failed.", runner)
            counter.failure()
            if counter.give_up:
                state = ServiceState.State.DOWN
                result = RunResult(started=(), deferred=(), failed=requests)
            else:
                state = ServiceState.State.WARNING
                result = RunResult(started=(), deferred=requests, failed=())
            service_state = ServiceState(
                service=runner.service_name, runner=runner.name,
                state=state, message=str(exc)
            )
            replace_one(slivka.db.database, service_state,
                        filter_keys=['service', 'runner'])
            return result

    def monitor_jobs(
            self,
            runner: Union[Runner, Type[Runner]],
            jobs: List[JobMetadata]
    ) -> Sequence[Tuple[JobMetadata, JobStatus]]:
        """ Checks status of jobs.

        Checks status of jobs using the provided runner or runner class
        and returns a list of those, whose status have changed.
        """
        counter = self._backoff_counters[runner]
        if not jobs or next(counter) > 0:
            return ()
        try:
            states = runner.batch_check_status(jobs)
            return [(job, state) for (job, state)
                    in zip(jobs, states) if job.state != state]
        except Exception as e:
            self.log.exception("Checking job status for %s failed.", runner)
            counter.failure()
            if counter.give_up:
                return [(job, JobStatus.ERROR) for job in jobs]
            else:
                return ()


class IntervalThread(threading.Thread):
    def __init__(self, interval, target,
                 name=None, args=None, kwargs=None):
        threading.Thread.__init__(self, name=name)
        self._target = target
        self._args = args or ()
        self._kwargs = kwargs or {}
        self.interval = interval
        self._finished = threading.Event()

    def cancel(self):
        """Stop the interval thread."""
        self._finished.set()

    def run(self) -> None:
        args, kwargs = self._args, self._kwargs
        try:
            while not self._finished.wait(self.interval):
                self._target(*args, **kwargs)
        finally:
            self._finished.set()
            del self._target, self._args, self._kwargs


class LimiterMeta(type):
    @classmethod
    def __prepare__(mcs, name, bases):
        return OrderedDict()

    def __new__(mcs, name, bases, attrs):
        cls = type.__new__(mcs, name, bases, attrs)
        cls.__limits__ = [
            (key[6:], func) for key, func in attrs.items()
            if key.startswith('limit_')
        ]
        for base in bases:
            cls.__limits__.extend(getattr(base, '__limits__', []))
        return cls


class Limiter(metaclass=LimiterMeta):
    """ The helper class that allows defining limits as methods.

    Extending classes can specify limits by declaring methods
    named ``limit_<runner name>`` that take one input parameters
    argument and return True or False whether this runner should
    be used. The methods are evaluated in order of declaration
    and the first one to return True is selected. Otherwise,
    the job is rejected.
    """
    def __call__(self, inputs):
        try:
            self.setup(inputs)
            return next(
                (name for name, func in self.__limits__ if func(self, inputs)),
                None
            )
        finally:
            self.__dict__.clear()

    def setup(self, inputs):
        pass


class DefaultLimiter(Limiter):
    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def limit_default(self, inputs):
        return True
