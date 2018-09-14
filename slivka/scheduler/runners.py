import logging
import os
import re
import shlex
import subprocess
from collections import defaultdict
from typing import Type, Optional, List, Tuple, Iterable

from slivka.scheduler.exceptions import QueueBrokenError, \
    QueueTemporarilyUnavailableError
from slivka.scheduler.execution_manager import Runner, JobHandler
from slivka.scheduler.task_queue import QueueServer
from slivka.utils import JobStatus

logger = logging.getLogger('slivka.scheduler.scheduler')


class ShellRunner(Runner):

    class Job(JobHandler):

        def __init__(self, process: subprocess.Popen):
            super().__init__()
            self._process = process

        @property
        def id(self) -> str:
            return str(self._process.pid)

        def get_status(self) -> JobStatus:
            try:
                status = self._process.poll()
            except Exception as e:
                raise QueueBrokenError from e
            if status is None:
                return JobStatus.RUNNING
            elif status == 0:
                return JobStatus.COMPLETED
            else:
                return JobStatus.FAILED

        def serialize(self) -> str:
            return ''

        @classmethod
        def deserialize(cls, serial) -> Optional['JobHandler']:
            return None

    def submit(self) -> 'JobHandler':
        return self.Job(subprocess.Popen(
            self.executable + self.args,
            stdout=open(os.path.join(self.cwd, 'stdout.txt'), 'w'),
            stderr=open(os.path.join(self.cwd, 'stderr.txt'), 'w'),
            cwd=self.cwd,
            universal_newlines=True
        ))

    @classmethod
    def get_job_handler_class(cls) -> Type['JobHandler']:
        return cls.Job


class LocalQueueRunner(Runner):

    class Job(JobHandler):
        def __init__(self, job_id):
            super().__init__()
            self._id = job_id

        @property
        def id(self) -> str:
            return self._id

        def get_status(self) -> JobStatus:
            try:
                return JobStatus(QueueServer.get_job_status(self.id))
            except ConnectionError:
                raise QueueTemporarilyUnavailableError

        def serialize(self) -> str:
            return self.id

        @classmethod
        def deserialize(cls, serial) -> 'JobHandler':
            return cls(serial)

    def submit(self) -> 'JobHandler':
        try:
            return self.Job(
                QueueServer.submit_job(
                    self.executable + self.args, self.cwd, self.env
                )
            )
        except ConnectionError:
            raise QueueTemporarilyUnavailableError

    @classmethod
    def get_job_handler_class(cls) -> Type['JobHandler']:
        return cls.Job


class GridEngineRunner(Runner):

    _job_submission_regex = re.compile(
        r'Your job (\d+) \(.+\) has been submitted'
    )
    _job_status_regex = re.compile(
        r'^\s*?(\d+).+?([rtdERTwhSszq]{1,3})\s+?[\d/]{10}\s+?[\d:]{8}'
    )
    _runner_script_template = (
        "#! /bin/sh\n"
        "touch started\n"
        "{command}\n"
        "echo $? > finished\n"
    )
    _status_letters = defaultdict(lambda: JobStatus.UNDEFINED, {
        'r': JobStatus.RUNNING,
        't': JobStatus.RUNNING,
        's': JobStatus.RUNNING,
        'qw': JobStatus.QUEUED,
        'T': JobStatus.QUEUED,
        'd': JobStatus.DELETED,
        'E': JobStatus.ERROR,
        'Eqw': JobStatus.ERROR
    })

    def submit(self) -> 'JobHandler':
        with open(os.path.join(self.cwd, 'runner_script.sh'), 'w') as f:
            f.write(self._runner_script_template.format(
                command=list2unix_command(self.executable + self.args)
            ))
        queue_command = (
            ['qsub'] +
            self.queue_args +
            ['-V', '-cwd', '-e', 'stderr.txt', '-o', 'stdout.txt'] +
            ['runner_script.sh']
        )
        process = subprocess.Popen(
            queue_command,
            stdout=subprocess.PIPE,
            cwd=self.cwd,
            env=self.env,
            universal_newlines=True
        )
        stdout, _ = process.communicate()
        match = self._job_submission_regex.match(stdout)
        if match is None:
            raise QueueBrokenError('%r doesn\'t match' % stdout)
        return self.Job(match.group(1))

    @classmethod
    def get_job_handler_class(cls) -> Type['JobHandler']:
        return cls.Job

    @staticmethod
    def get_job_status(job_handlers: List['JobHandler']) \
            -> Iterable[Tuple['JobHandler', JobStatus]]:
        process = subprocess.Popen(
            ['qstat'],
            stdout=subprocess.PIPE,
            universal_newlines=True
        )
        stdout, _ = process.communicate()
        job_status = {}
        for match in GridEngineRunner._job_status_regex.findall(stdout):
            job_id, status = match
            job_status[job_id] = GridEngineRunner._status_letters[status]
        for handler in job_handlers:
            status = job_status.get(handler.id)
            if status is None:
                if os.path.exists(os.path.join(handler.cwd, 'finished')):
                    status = JobStatus.COMPLETED
                else:
                    status = JobStatus.RUNNING
            yield (handler, status)

    class Job(JobHandler):
        @property
        def id(self) -> str:
            return self._id

        def get_status(self) -> JobStatus:
            raise NotImplementedError("Get single job status not supported")

        def serialize(self) -> str:
            return self.id

        @classmethod
        def deserialize(cls, serial) -> 'JobHandler':
            return cls(serial)

        def __init__(self, job_id):
            super().__init__()
            self._id = job_id


def list2unix_command(args):
    return ' '.join(shlex.quote(a) for a in args)