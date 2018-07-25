import logging
import os
import subprocess
from typing import Type, Optional

from slivka.scheduler.exceptions import QueueBrokenError, \
    QueueTemporarilyUnavailableError
from slivka.scheduler.execution_manager import Runner, JobHandler
from slivka.scheduler.task_queue import QueueServer
from slivka.utils import JobStatus

logger = logging.getLogger('slivka.scheduler.scheduler')


class ShellRunner(Runner):

    class Job(JobHandler):

        def __init__(self, process: subprocess.Popen):
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


# class GridEngineExec(Executor):
#
#     job_submission_regex = re.compile(
#         r'Your job (\d+) \(.+\) has been submitted'
#     )
#
#     def submit(self, values, cwd):
#         queue_command = [
#             'qsub', '-cwd', '-e', 'stderr.txt', '-o', 'stdout.txt'
#         ] + self.qargs
#         process = subprocess.Popen(
#             queue_command,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             stdin=subprocess.PIPE,
#             cwd=cwd,
#             env=self.env,
#             universal_newlines=True
#         )
#         command_chunks = self.bin + self.get_options(values)
#         command = ' '.join(shlex.quote(s) for s in command_chunks)
#         stdin = ("echo > started;\n"
#                  "%s;\n"
#                  "echo > finished;") % command
#         stdout, stderr = process.communicate(stdin)
#         match = self.job_submission_regex.match(stdout)
#         return match.group(1)
#
#     @staticmethod
#     def get_job_wrapper_class():
#         return GridEngineJob
#
#
# class GridEngineJob(Job):
#
#     job_status_regex_pattern = (
#         r'^{0}\s+[\d\.]+\s+.*?\s+[\w-]+\s+(\w{{1,3}})\s+[\d/]+\s+[\d:]+\s+'
#         r'[\w@\.-]*\s+\d+$'
#     )
#
#     def get_status(self, job_id):
#         username = getpass.getuser()
#         process = subprocess.Popen(
#             "qstat -u '%s'" % (username or '*'),
#             stdout=subprocess.PIPE,
#             shell=True,
#             universal_newlines=True
#         )
#         out, err = process.communicate()
#         regex = self.job_status_regex_pattern.format(job_id)
#         match = re.search(regex, out, re.MULTILINE)
#         if match is None:
#             try:
#                 time_started = os.path.getmtime(
#                     os.path.join(self.cwd, 'started'))
#             except FileNotFoundError:
#                 return self.STATUS_QUEUED
#             try:
#                 time_finished = os.path.getmtime(
#                     os.path.join(self.cwd, 'finished'))
#             except FileNotFoundError:
#                 return self.STATUS_RUNNING
#             else:
#                 if time_finished >= time_started:
#                     return self.STATUS_COMPLETED
#                 else:
#                     return self.STATUS_RUNNING
#         else:
#             status = match.group(1)
#             if status == 'r' or status == 't':
#                 return self.STATUS_RUNNING
#             elif status == 'qw' or status == 'T':
#                 return self.STATUS_QUEUED
#             elif status == 'd':
#                 return self.STATUS_DELETED
#             else:
#                 raise QueueTemporarilyUnavailableError
#
#     def get_result(self, job_id):
#         return 0
