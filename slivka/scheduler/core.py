import logging
from collections import defaultdict, namedtuple, OrderedDict
from importlib import import_module

import threading
from functools import partial
from pymongo import UpdateMany, UpdateOne
from typing import Iterable, Tuple, Dict, List, Any, Type, Union, DefaultDict

import slivka.db
from slivka.db.documents import JobRequest, JobMetadata
from slivka.db.helpers import insert_many
from slivka.scheduler.runners.runner import RunnerID, Runner
from slivka.utils import JobStatus, BackoffCounter


def _fetch_pending_requests(database) -> Iterable[JobRequest]:
    requests = JobRequest.collection(database).find(
        {'status': JobStatus.PENDING})
    return (JobRequest(**kwargs) for kwargs in requests)


def get_classpath(cls):
    return cls.__module__ + '.' + cls.__name__


RunResult = namedtuple('RunResult', 'started, deferred, failed')

# sentinel valued corresponding to the rejected and error requests
REJECTED = object()
ERROR = object()


class Scheduler:
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self._finished = threading.Event()
        self.runners = {}  # type: Dict[RunnerID, Runner]
        self.limiters = defaultdict(DefaultLimiter)  # type: Dict[str, Limiter]
        self._backoff_counters = defaultdict(
            partial(BackoffCounter, max_tries=10)
        )  # type: DefaultDict[Any, BackoffCounter]
        self._accepted_requests = defaultdict(list)  # type: Dict[Runner, List[JobRequest]]
        self._running_jobs = defaultdict(list)  # type: Dict[Type[Runner], List[JobMetadata]]

    def is_running(self): return not self._finished.is_set()
    is_running = property(is_running)

    def set_failure_limit(self, limit):
        factory = partial(BackoffCounter, max_tries=limit)
        self._backoff_counters.default_factory = factory
        for counter in self._backoff_counters.values():
            counter.max_tries = limit

    def add_runner(self, runner: Runner):
        self.runners[runner.id] = runner

    def load_runners(self, service_name, conf_dict):
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
            self.runners[runner_id] = cls(
                conf_dict, id=RunnerID(service_name, name), **kwargs
            )

    def stop(self):
        self._finished.set()

    def run_forever(self):
        if self._finished.is_set():
            raise RuntimeError
        try:
            while not self._finished.wait(1):
                self.run_cycle()
        except KeyboardInterrupt:
            self.stop()

    def run_cycle(self):
        database = slivka.db.database
        request_operations = []
        # fetching new requests
        new_requests = _fetch_pending_requests(database)
        grouped = self.group_requests(new_requests)
        rejected = grouped.pop(REJECTED, ())
        if rejected:
            request_operations.append(UpdateMany(
                {'_id': {'$in': [req.id for req in rejected]}},
                {'$set': {'status': JobStatus.REJECTED}}
            ))
        error = grouped.pop(ERROR, ())
        if error:
            request_operations.append(UpdateMany(
                {'_id': {'$in': [req.id for req in error]}},
                {'$set': {'status': JobStatus.ERROR}}
            ))
        for runner, requests in grouped.items():
            request_operations.append(UpdateMany(
                {'_id': {'$in': [req.id for req in requests]}},
                {'$set': {'status': JobStatus.ACCEPTED}}
            ))
            self._accepted_requests[runner].extend(requests)
        collection = JobRequest.collection(database)
        if request_operations:
            collection.bulk_write(request_operations, ordered=False)
            request_operations.clear()

        # starting accepted requests
        for runner, requests in self._accepted_requests.items():
            if not requests:
                continue
            new_jobs = []
            started, deferred, failed = self.run_requests(runner, requests)
            self._accepted_requests[runner] = list(deferred)
            for request, job in started:
                request_operations.append(UpdateOne(
                    {'_id': request.id},
                    {'$set': {'status': JobStatus.QUEUED}}
                ))
                new_jobs.append(JobMetadata(
                    uuid=request.uuid,
                    service=request.service,
                    work_dir=job.cwd,
                    runner_class=get_classpath(type(runner)),
                    job_id=job.id,
                    status=JobStatus.QUEUED
                ))
            self._running_jobs[type(runner)].extend(new_jobs)
            insert_many(database, new_jobs)
            request_operations.append(UpdateMany(
                {'_id': {'$in': [req.id for req in failed]}},
                {'$set': {'status': JobStatus.ERROR}}
            ))
        if request_operations:
            collection.bulk_write(request_operations, ordered=False)
            request_operations.clear()

        # monitoring jobs
        job_operations = []
        for runner, jobs in self._running_jobs.items():
            if not jobs:
                continue
            update = self.monitor_jobs(runner, jobs)
            for (job, state) in update:
                job.state = state
                job_operations.append(UpdateOne(
                    {'_id': job.id}, {'$set': {'status': state}}
                ))
                request_operations.append(UpdateOne(
                    {'uuid': job.uuid}, {'$set': {'status': state}}
                ))
            jobs[:] = (
                job for job in jobs if not job.state.is_finished()
            )
        if request_operations:
            (JobRequest.collection(database)
                       .bulk_write(request_operations, ordered=False))
        if job_operations:
            (JobMetadata.collection(database)
                        .bulk_write(job_operations, ordered=False))

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

    def run_requests(self, runner: Runner, requests: List[JobRequest]) -> RunResult:
        """Run all requests in the list using the runner."""
        counter = self._backoff_counters[runner]
        if not requests or next(counter) > 0:
            return RunResult(started=(), deferred=requests, failed=())
        try:
            jobs = runner.batch_run([req.inputs for req in requests])
            return RunResult(
                started=zip(requests, jobs), deferred=(), failed=()
            )
        except Exception:
            self.log.exception("Running requests with %s failed.", runner)
            counter.failure()
            print('counter', counter.current)
            if counter.give_up:
                return RunResult(started=(), deferred=(), failed=requests)
            else:
                return RunResult(started=(), deferred=requests, failed=())

    def monitor_jobs(
            self,
            runner: Union[Runner, Type[Runner]],
            jobs: List[JobMetadata]
    ) -> Iterable[Tuple[JobMetadata, JobStatus]]:
        """Checks status of jobs and returns modified."""
        counter = self._backoff_counters[runner]
        if not jobs or next(counter) > 0:
            return ()
        try:
            states = runner.batch_check_status(jobs)
            print(states)
            return ((job, state) for (job, state)
                    in zip(jobs, states) if job.state != state)
        except Exception as e:
            counter.failure()
            if counter.give_up:
                return ((job, JobStatus.ERROR) for job in jobs)
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
