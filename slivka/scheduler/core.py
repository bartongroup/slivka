import time
import logging
from collections import deque, defaultdict, OrderedDict, namedtuple
from importlib import import_module
from itertools import islice
from typing import Dict, Type, Optional, List

from slivka import JobStatus
from slivka.db import mongo
from slivka.db.documents import JobRequest, JobMetadata
from .runners import *

__all__ = ['Scheduler', 'Limiter', 'DefaultLimiter']


def get_classpath(cls):
    return cls.__module__ + '.' + cls.__name__


class Scheduler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.requests = deque()
        self._is_running = False
        self.runner_selector = RunnerSelector()
        self.running_jobs = defaultdict(list)  # type: Dict[Type[Runner], List[JobMetadata]]
        self.reload()

    def load_service(self, service, cmd_def):
        self.runner_selector.add_runners(service, cmd_def)

    @property
    def is_running(self):
        return self._is_running

    def stop(self):
        self._is_running = False

    def reload(self):
        """Reloads running jobs from the database."""
        running_jobs = JobMetadata.find(
            mongo.slivkadb,
            {'$or': [
                {'status': JobStatus.QUEUED},
                {'status': JobStatus.RUNNING}
            ]}
        )
        for job in running_jobs:
            mod, cls = job['runner_class'].rsplit('.', 1)
            runner_cls = getattr(import_module(mod), cls)
            self.running_jobs[runner_cls].append(job)

    def run_forever(self):
        if self.is_running:
            raise RuntimeError("Scheduler is already running.")
        self._is_running = True
        self.logger.info('scheduler started')
        try:
            while self.is_running:
                self.run_new_requests()
                self.update_running_jobs()
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.stop()

    def run_new_requests(self, limit=None):
        new_requests = JobRequest.find(
            mongo.slivkadb, status=JobStatus.PENDING
        )
        runner_requests = defaultdict(list)  # type: Dict[Runner, List[JobRequest]]
        for request in islice(new_requests, limit):
            runner = self.runner_selector.select_runner(request.service, request.inputs)
            runner_requests[runner].append(request)
        for runner, requests in runner_requests.items():
            if self.logger.isEnabledFor(logging.INFO):
                for request in requests:
                    self.logger.info(
                        'starting job %s with %s',
                        request.uuid, runner.__class__.__name__
                    )
            runs = runner.batch_run([r.inputs for r in requests])
            for run, request in zip(runs, requests):
                if isinstance(run, RunInfo):
                    request.update_self(mongo.slivkadb, status=JobStatus.QUEUED)
                    job = JobMetadata(
                        uuid=request['uuid'],
                        service=request['service'],
                        work_dir=run.cwd,
                        runner_class=get_classpath(runner.__class__),
                        job_id=run.id,
                        status=JobStatus.QUEUED
                    )
                    job.insert(mongo.slivkadb)
                    self.running_jobs[runner.__class__].append(job)

    def update_running_jobs(self):
        for runner_cls, jobs in self.running_jobs.items():
            if len(jobs) == 0:
                continue
            stats = runner_cls.batch_check_status(job['job_id'] for job in jobs)
            for job, new_status in zip(jobs, stats):
                if job['status'] != new_status:
                    self.logger.info(
                        "job %s status changed to %s", job.uuid, new_status.name
                    )
                    job.update_self(mongo.slivkadb, status=new_status)
                    JobRequest.update_one(
                        mongo.slivkadb,
                        {'uuid': job['uuid']},
                        {'status': new_status}
                    )
            jobs[:] = (
                job for job in jobs
                if not JobStatus(job['status']).is_finished()
            )


RunnerID = namedtuple('RunnerID', 'service, name')


class RunnerSelector:
    def __init__(self):
        self.runners = {}  # type: Dict[RunnerID, Runner]
        self.limiters = {}  # type: Dict[str, Limiter]

    def add_runners(self, service, cmd_def):
        classpath = cmd_def.get('limiter', get_classpath(DefaultLimiter))
        mod, attr = classpath.rsplit('.', 1)
        self.limiters[service] = getattr(import_module(mod), attr)()

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
            return None
        else:
            return self.runners[service, runner_name]


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
