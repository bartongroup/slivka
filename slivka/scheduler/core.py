import logging
import threading
from collections import defaultdict, OrderedDict, namedtuple
from importlib import import_module

import time
from functools import partial
from typing import Dict, Type, Optional, List, Mapping, Any, DefaultDict

import slivka.db
from slivka import JobStatus
from slivka.db.documents import JobRequest, JobMetadata, ServiceState, ServiceStatus
from slivka.utils import BackoffCounter
from .runners import *
from .service_test import TestJob

__all__ = ['Scheduler', 'Limiter', 'DefaultLimiter', 'RunnerManager']


def get_classpath(cls):
    return cls.__module__ + '.' + cls.__name__


RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
REGULAR = "\033[0m"


def colored(text, color):
    return color + text + REGULAR


class Scheduler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._is_running = False
        self.runner_selector = RunnerManager()
        self.running_jobs = defaultdict(list)  # type: Dict[Type[Runner], List[JobMetadata]]
        self._backoff_counters = defaultdict(partial(BackoffCounter, max_tries=10))  # type: Dict[Any, BackoffCounter]
        self._accepted_requests = defaultdict(list)  # type: DefaultDict[Runner, List[JobRequest]]
        self._testing_thread = IntervalThread(interval=3600, target=self.test_services)

    def load_service(self, service, cmd_def):
        self.runner_selector.add_runners(service, cmd_def)

    @property
    def is_running(self):
        return self._is_running

    def stop(self):
        self.logger.info("Stopping.")
        self._testing_thread.cancel()
        self._is_running = False

    def reload(self):
        """Reloads running jobs from the database and change accepted back to pending."""
        running_jobs = JobMetadata.find(
            slivka.db.database,
            {'$or': [
                {'status': JobStatus.QUEUED},
                {'status': JobStatus.RUNNING}
            ]}
        )
        for job in running_jobs:
            mod, cls = job['runner_class'].rsplit('.', 1)
            runner_cls = getattr(import_module(mod), cls)
            self.running_jobs[runner_cls].append(job)
        JobRequest.get_collection(slivka.db.database).update_many(
            filter={'status': JobStatus.ACCEPTED},
            update={'$set': {'status': JobStatus.PENDING}}
        )

    def run_forever(self):
        if self.is_running:
            raise RuntimeError("Scheduler is already running.")
        self._is_running = True
        self.test_services()
        self._testing_thread.start()
        self.reload()
        self.logger.info('Scheduler started')
        try:
            while self.is_running:
                self.fetch_pending_requests(self._accepted_requests)
                self.run_requests(self._accepted_requests)
                self.update_running_jobs()
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
        self.logger.info('Stopped')

    def test_services(self):
        report = self.runner_selector.test_services()
        to_insert = []
        for runner_id, status in report.items():
            state, reason = status
            service_status = ServiceStatus(
                service=runner_id.service,
                runner=runner_id.name,
                state=ServiceState.UNKNOWN
            )
            if state == 'OK':
                print(runner_id, colored("[OK]", GREEN))
                service_status.state = ServiceState.OK
            elif state == 'FAILED':
                print(runner_id, colored("[FAILED]", YELLOW), reason)
                service_status.state = ServiceState.BROKEN
            elif state == 'ERROR':
                print(runner_id, colored("[ERROR]", RED), reason)
                service_status.state = ServiceState.BROKEN
            else:
                print(runner_id, state, reason)
            to_insert.append(service_status)
        collection = ServiceStatus.get_collection(slivka.db.database)
        collection.insert_many(to_insert, ordered=False)

    def fetch_pending_requests(self, accepted: DefaultDict[Runner, List[JobRequest]]):
        """Fetches pending requests from the database and populated provided dict

        :param accepted: Dictionary to be populated with accepted requests
        :return: None
        """
        requests = JobRequest.find(
            slivka.db.database, status=JobStatus.PENDING
        )
        accepted_id = []
        rejected_id = []
        for request in requests:
            runner = self.runner_selector.select_runner(request.service, request.inputs)
            if runner is not None:
                accepted_id.append(request['_id'])
                accepted[runner].append(request)
            else:
                rejected_id.append(request['_id'])
        collection = JobRequest.get_collection(slivka.db.database)
        collection.update_many(
            {'_id': {'$in': accepted_id}},
            {'$set': {'status': JobStatus.ACCEPTED}}
        )
        collection.update_many(
            {'_id': {'$in': rejected_id}},
            {'$set': {'status': JobStatus.REJECTED}}
        )

    def run_requests(self,
                     accepted_requests: Mapping[Runner, List[JobRequest]],
                     limit: int = None):
        for runner, requests in accepted_requests.items():
            counter = self._backoff_counters[runner]
            if not requests or next(counter) > 0:
                continue
            try:
                self.logger.info("Submitting batch %s",
                                 ', '.join(r['uuid'] for r in requests))
                jobs = runner.batch_run([r['inputs'] for r in requests])
            except:
                counter.failure()
                if counter.give_up:
                    JobRequest.get_collection(slivka.db.database).update_many(
                        {'_id': {'$in': [r['_id'] for r in requests]}},
                        {'$set': {'status': JobStatus.ERROR}}
                    )
                    requests.clear()
                    self.logger.exception(
                        "Submitting jobs using %s failed. Giving up.",
                        runner, exc_info=True
                    )
                else:
                    self.logger.exception(
                        "Submitting jobs using %s failed. Retrying in %d iterations.",
                        runner, counter.current, exc_info=True
                    )
            else:
                for job, request in zip(jobs, requests):
                    j = JobMetadata(
                        uuid=request['uuid'],
                        service=request['service'],
                        work_dir=job.cwd,
                        runner_class=get_classpath(runner.__class__),
                        job_id=job.id,
                        status=JobStatus.QUEUED
                    )
                    j.insert(slivka.db.database)
                    self.running_jobs[runner.__class__].append(j)
                JobRequest.get_collection(slivka.db.database).update_many(
                    {'_id': {'$in': [r['_id'] for r in requests]}},
                    {'$set': {'status': JobStatus.QUEUED}}
                )
                requests.clear()

    def update_running_jobs(self):
        for runner_cls, jobs in self.running_jobs.items():
            counter = self._backoff_counters[runner_cls]
            if len(jobs) == 0 or next(counter) > 0:
                continue
            try:
                states = runner_cls.batch_check_status(jobs)
            except Exception:
                if counter.give_up:
                    for cls in (JobMetadata, JobRequest):
                        collection = cls.get_collection(slivka.db.database)
                        collection.update_many(
                            {'uuid': {'$in': [j['uuid'] for j in jobs]}},
                            {'$set': {'status': JobStatus.ERROR}}
                        )
                    for job in jobs:
                        job['status'] = JobStatus.ERROR
                counter.failure()
                self.logger.exception(
                    "Checking job status using %s failed.", runner_cls.__name__,
                    exc_info=True
                )
            else:
                for job, new_state in zip(jobs, states):
                    if job['status'] != new_state:
                        self.logger.info(
                            "Job %s status changed to %s", job.uuid, new_state.name
                        )
                        job.update_self(slivka.db.database, status=new_state)
                        JobRequest.update_one(
                            slivka.db.database,
                            {'uuid': job['uuid']},
                            {'status': new_state}
                        )
            jobs[:] = (
                job for job in jobs
                if not JobStatus(job['status']).is_finished()
            )


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


RunnerID = namedtuple('RunnerID', 'service, name')


class RunnerManager:
    def __init__(self):
        self.runners = {}  # type: Dict[RunnerID, Runner]
        self.limiters = {}  # type: Dict[str, Limiter]
        self._tests = {}
        self._null_runner = None

    def add_runners(self, service, cmd_def):
        classpath = cmd_def.get('limiter', get_classpath(DefaultLimiter))
        mod, attr = classpath.rsplit('.', 1)
        self.limiters[service] = getattr(import_module(mod), attr)()
        test_dict = cmd_def.get('test')
        if test_dict is not None:
            self._tests[service] = TestJob(test_dict['inputs'])

        for name, conf in cmd_def['runners'].items():
            if '.' in conf['class']:
                mod, attr = conf['class'].rsplit('.', 1)
            else:
                mod, attr = 'slivka.scheduler.runners', conf['class']
            cls = getattr(import_module(mod), attr)  # type: Type[Runner]
            kwargs = conf.get('parameters', {})
            runner_id = RunnerID(service, name)
            self.runners[runner_id] = cls(
                cmd_def, name="%s-%s" % runner_id, **kwargs
            )

    def select_runner(self, service, inputs) -> Optional[Runner]:
        runner_name = self.limiters[service](inputs)
        if runner_name is None:
            return self._null_runner
        else:
            return self.runners[service, runner_name]

    def test_services(self):
        report = {}
        for service_id, runner in self.runners.items():
            test = self._tests.get(service_id.service)
            if test is None:
                report[service_id] = ('NO TEST', None)
                continue
            try:
                state = test(runner, dir=slivka.settings.jobs_dir)
            except Exception as e:
                report[service_id] = ('ERROR', e)
            else:
                if state == JobStatus.COMPLETED:
                    report[service_id] = ('OK', None)
                else:
                    report[service_id] = ('FAILED', state.name)
        return report


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
