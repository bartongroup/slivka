import contextlib
import inspect
import logging
import os
import threading
from collections import defaultdict, namedtuple, OrderedDict
from datetime import datetime
from functools import partial
from typing import (Iterable, Dict, List, Any, Union, DefaultDict,
                    Sequence, Callable, Tuple)

import attrs
import pymongo.errors

import slivka.conf
import slivka.db
from slivka.db.documents import JobRequest, CancelRequest
from slivka.db.helpers import delete_many, push_many
from slivka.utils import JobStatus, BackoffCounter
from slivka.utils import retry_call
from .runners import Job as JobTuple
from .runners.runner import RunnerID, Runner
from ..utils.path import request_id_to_job_path


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

    def __init__(self, jobs_directory=None):
        self.log = logging.getLogger(__name__)
        self._finished = threading.Event()
        self.jobs_directory = jobs_directory or slivka.conf.settings.directory.jobs
        self.runners: Dict[RunnerID, Runner] = {}
        self.selectors: Dict[str, Callable] = defaultdict(lambda: BaseSelector.default)
        self._backoff_counters: DefaultDict[Any, BackoffCounter] = \
            defaultdict(partial(BackoffCounter, max_tries=10))
        self._auto_reconnect_handler = partial(_auto_reconnect_handler, self.log)

    @property
    def is_running(self):
        """ Checks whether the scheduler is running. """
        return not self._finished.is_set()

    def set_failure_limit(self, limit):
        """ Sets the limit of allowed exceptions before job is rejected. """
        factory = partial(BackoffCounter, max_tries=limit)
        self._backoff_counters.default_factory = factory
        for counter in self._backoff_counters.values():
            counter.max_tries = limit

    def add_runner(self, runner: Runner):
        self.runners[runner.id] = runner

    def list_runners(self, service: str):
        return [
            runner for runner_id, runner in self.runners.items()
            if runner_id.service == service
        ]

    def add_selector(self, service: str, selector: Callable):
        self.selectors[service] = selector

    def stop(self):
        self._finished.set()

    def run_forever(self):
        """ Starts the main loop

        The main loop is running until the :py:meth:`stop` is called.
        It repeatedly performs work cycles with one second delay
        between them.
        """
        if self._finished.is_set():
            raise RuntimeError("scheduler can only be started once")
        self.log.info('scheduler started')
        try:
            while not self._finished.wait(1):
                self.main_loop()
        except KeyboardInterrupt:
            self.stop()

    def main_loop(self):
        database = slivka.db.database

        # fetching new requests
        self._assign_runners(database)

        # Fetch cancel requests and update cancelled job states to
        # DELETED if they were PENDING or ACCEPTED; or CANCELLING if QUEUED or RUNNING
        self._stop_cancelled(database)

        # starting ACCEPTED requests
        self._run_accepted(database)

        # monitoring jobs
        self._update_running(database)

    def _assign_runners(self, database):
        """Assigns new status and runner to pending requests.

        For each pending request in the database, uses selector
        to find the appropriate runner or gives a REJECTED or ERROR status
        """
        auto_reconnect_handler = self._auto_reconnect_handler
        new_requests = retry_call(
            partial(_fetch_pending_requests, database),
            pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
        )
        grouped = self.group_requests(new_requests)
        rejected = grouped.pop(REJECTED, ())
        if rejected:
            retry_call(
                partial(_bulk_set_status, database, rejected, JobStatus.REJECTED),
                pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
            )
        error = grouped.pop(ERROR, ())
        if error:
            retry_call(
                partial(_bulk_set_status, database, error, JobStatus.ERROR),
                pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
            )
        for runner, requests in grouped.items():
            retry_call(
                partial(_bulk_set_accepted, database, requests, runner),
                pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
            )

    def group_requests(self, requests: Iterable[JobRequest]) \
            -> Dict[Union[Runner, object], List[JobRequest]]:
        """Group requests to their corresponding runners or reject."""
        grouped = defaultdict(list)
        for request in requests:
            selector = self.selectors[request.service]
            kwargs = {}
            if "context" in inspect.signature(selector).parameters:
                runners = self.list_runners(request.service)
                kwargs["context"] = SelectorContext(
                    service=request.service,
                    runners=[r.name for r in runners],
                    runner_options={
                        r.name: r.selector_options
                        for r in runners
                    }
                )
            runner_name = selector(request.inputs, **kwargs)
            if runner_name is None:
                grouped[REJECTED].append(request)
            else:
                try:
                    runner = self.runners[request.service, runner_name]
                    grouped[runner].append(request)
                except KeyError:
                    grouped[ERROR].append(request)
                    self.log.exception(
                        "runner \"%s\" does not exist for service \"%s\"",
                        runner_name, request.service
                    )
        return grouped

    def _stop_cancelled(self, database):
        auto_reconnect_handler = self._auto_reconnect_handler
        cancel_requests = retry_call(
            partial(_fetch_cancel_requests, database),
            exceptions=pymongo.errors.AutoReconnect,
            handler=auto_reconnect_handler
        )
        if cancel_requests:
            job_ids = [cr.job_id for cr in cancel_requests]
            fn = partial(_bulk_set_status_filter_by_status, database, job_ids,
                         (JobStatus.PENDING, JobStatus.ACCEPTED), JobStatus.DELETED)
            retry_call(
                fn, pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
            )
            fn = partial(_bulk_set_status_filter_by_status, database, job_ids,
                         (JobStatus.QUEUED, JobStatus.RUNNING), JobStatus.CANCELLING)
            retry_call(
                fn, pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
            )
            cursor = JobRequest.find(database, status=JobStatus.CANCELLING)
            cancelling = retry_call(
                partial(list, cursor), pymongo.errors.AutoReconnect,
                handler=auto_reconnect_handler
            )
            for request in cancelling:
                assert request.runner is not None
                # fixme: do not blindly trust data from the database
                #        the runner may not exist
                runner = self.runners[request.service, request.runner]
                job = request.job
                assert job is not None
                with contextlib.suppress(OSError):
                    runner.cancel(JobTuple(job.job_id, job.work_dir))
            retry_call(
                partial(delete_many, database, cancel_requests),
                pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
            )

    def _run_accepted(self, database):
        auto_reconnect_handler = self._auto_reconnect_handler
        items = retry_call(
            partial(_fetch_requests_for_status, database, filter=JobStatus.ACCEPTED),
            pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
        )
        for item in items:
            requests = [JobRequest(**kw) for kw in item['requests']]
            try:
                try:
                    runner = self.runners[RunnerID(**item['_id'])]
                except KeyError:
                    self.log.exception("Runner does not exist.")
                    raise ExecutionFailed(None)
                self.log.debug("Starting jobs with %s.", runner)
                started = self._start_requests(runner, requests)
                queued = []
                for request, job in started:
                    queued.append(request)
                    request.job = JobRequest.Job(
                        job_id=job.id,
                        work_dir=job.cwd
                    )
                    request.status = JobStatus.QUEUED
                if queued:
                    retry_call(
                        partial(push_many, database, queued),
                        pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
                    )
            except ExecutionDeferred as e:
                self.log.debug("Runner %s did not start jobs. Retrying.",
                               e.runner)
            except ExecutionFailed:
                retry_call(
                    partial(_bulk_set_status, database, requests, JobStatus.ERROR),
                    pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
                )
                self.log.exception("Starting jobs failed.")

    def _start_requests(self, runner: Runner, requests: List[JobRequest]) \
            -> Iterable[Tuple[JobRequest, JobTuple]]:
        """ Run all requests with the supplied runner.

        Runs all the job requests using the provided runner implementing
        :py:class:`Runner` and returns an iterable of request-job pairs.
        If jobs fail to start, either :py:class:`ExecutionDeferred` or
        :py:class:`ExecutionFailed` is raised to indicate whether the
        batch execution was deferred or failed and should not be retried.
        """
        counter = self._backoff_counters[runner.start]
        if not requests or next(counter) > 0:
            raise ExecutionDeferred(runner)
        try:
            jobs = runner.batch_start(
                [req.inputs for req in requests],
                [request_id_to_job_path(self.jobs_directory, req.b64id) for req in requests]
            )
            return zip(requests, jobs)
        except Exception as e:
            self.log.exception("Starting jobs with %s failed.", runner)
            counter.failure()
            if counter.give_up:
                exc = ExecutionFailed(runner)
            else:
                exc = ExecutionDeferred(runner)
            raise exc from e

    def _update_running(self, database):
        auto_reconnect_handler = self._auto_reconnect_handler
        items = retry_call(
            partial(_fetch_requests_for_status, database,
                    filter={'$in': (JobStatus.QUEUED, JobStatus.RUNNING)}),
            pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
        )
        for item in items:
            _id = RunnerID(**item['_id'])
            requests = [JobRequest(**kw) for kw in item['requests']]
            ts = datetime.now()
            try:
                runner = self.runners[_id]
            except KeyError:
                self.log.exception("Runner (%s, %s) does not exist",
                                   _id.service, _id.runner)
                for req in requests:
                    req.status = JobStatus.ERROR
                updated = requests
            else:
                updated = self.monitor_jobs(runner, requests)
            if not updated:
                continue
            for request in updated:
                if request.status.is_finished():
                    request.completion_time = ts
            retry_call(
                partial(push_many, database, updated),
                pymongo.errors.AutoReconnect, handler=auto_reconnect_handler
            )

    def monitor_jobs(self, runner: Runner, requests: List[JobRequest]) \
            -> Sequence[JobRequest]:
        """ Checks status of jobs.

        Checks and updates status of requests using the provided runner
        or runner class and returns a list of those, whose status have changed.
        """
        counter = self._backoff_counters[runner.check_status]
        if not requests or next(counter) > 0:
            return ()
        updated = []
        try:
            statuses = runner.batch_check_status(
                [JobTuple(r.job.job_id, r.job.cwd) for r in requests])
            for request, status in zip(requests, statuses):
                if request.status != status:
                    request.status = status
                    updated.append(request)
            if updated and all(r.status == JobStatus.ERROR for r in updated):
                self.log.exception(
                    "Jobs of %s exited with error state", runner)
                counter.failure()
        except Exception:
            self.log.exception("Checking job status for %s failed.", runner)
            counter.failure()
            if counter.give_up:
                for request in requests:
                    request.status = JobStatus.ERROR
                updated.extend(requests)
        return updated


def _auto_reconnect_handler(log, exception):
    assert isinstance(exception, pymongo.errors.AutoReconnect)
    log.exception("Could not connect to mongo server.", exc_info=True)


def _fetch_pending_requests(database) -> Iterable[JobRequest]:
    requests = (JobRequest
                .collection(database)
                .find({'status': JobStatus.PENDING}))
    return [JobRequest(**kwargs) for kwargs in requests]


def _bulk_set_status(database, requests, status):
    JobRequest.collection(database).update_many(
        {'_id': {'$in': [req.id for req in requests]}},
        {'$set': {'status': status}}
    )


def _bulk_set_accepted(database, requests, runner):
    JobRequest.collection(database).update_many(
        {'_id': {'$in': [req.id for req in requests]}},
        {'$set': {
            'status': JobStatus.ACCEPTED,
            'runner': runner.name
        }}
    )


def _fetch_cancel_requests(database) -> List[CancelRequest]:
    return list(CancelRequest.find(database))


def _bulk_set_status_filter_by_status(database, job_ids, from_statuses, to_status):
    JobRequest.collection(database).update_many(
        {'_id': {'$in': job_ids},
         'status': {'$in': from_statuses}},
        {'$set': {'status': to_status}}
    )


def _fetch_requests_for_status(database, filter):
    return list(JobRequest.collection(database).aggregate([
        {'$match': {'status': filter}},
        {'$group': {
            '_id': {'service': '$service',
                    'runner': '$runner'},
            'requests': {'$push': '$$CURRENT'}
        }}
    ]))


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


@attrs.define(frozen=True)
class SelectorContext:
    service: str
    runners: List[str]
    runner_options: Dict[str, Dict[str, Any]]


class SelectorMeta(type):
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


class BaseSelector(metaclass=SelectorMeta):
    """ The helper class that allows defining limits as methods.

    Extending classes can specify limits by declaring methods
    named ``limit_<runner name>`` that take one input parameters
    argument and return True or False whether this runner should
    be used. The methods are evaluated in order of declaration
    and the first one to return True is selected. Otherwise,
    the job is rejected.
    """
    def __call__(self, inputs, context):
        try:
            self.setup(inputs)
            return next(
                (
                    name for name, func in self.__limits__
                    if func(self, inputs, **(context.runner_options.get(name, {})))
                ),
                None
            )
        finally:
            self.__dict__.clear()

    def setup(self, inputs):
        pass

    @staticmethod
    def default(_inputs):
        return "default"


class ExecutionDeferred(Exception):
    def __init__(self, runner):
        super().__init__(runner)
        self.runner = runner


class ExecutionFailed(Exception):
    pass
