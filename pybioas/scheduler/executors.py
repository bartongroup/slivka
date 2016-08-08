import os
import shlex
import subprocess
import sys
import uuid

import pybioas
from .command import CommandOption, FileResult, PatternFileResult
from .task_queue import QueueServer


class JobMixin:
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_EXCEPTION = 'exception'
    STATUS_FAILED = 'failed'
    STATUS_SUCCESS = 'success'

    def get_status(self, job_id):
        raise NotImplementedError

    def get_result(self, job_id):
        raise NotImplementedError


# noinspection PyAbstractClass
class Executor(JobMixin):

    def __init__(self, *, bin="", options=None,
                 qargs=None, file_results=None, env=None):
        """
        :param bin: executable command
        :type bin: str
        :param options: list of command options
        :type options: list[CommandOption]
        :param qargs: queue engine arguments
        :type qargs: list[str]
        :param file_results: list of command outputs
        :type file_results: list[FileResult]
        :param env: dictionary of environment variables to use
        :type env: dict[str, str]
        """
        self._qargs = qargs or []
        self._bin = shlex.split(bin)
        self._options = options or []
        self._file_results = file_results or []
        self._env = env or {}

    def __call__(self, values):
        cwd = os.path.join(pybioas.settings.WORK_DIR, uuid.uuid4().hex)
        os.mkdir(cwd)
        job_id = self.submit(values, cwd)
        job = Job(job_id, cwd, self)
        job.get_status = self.get_status.__func__.__get__(job, Job)
        job.get_result = self.get_result.__func__.__get__(job, Job)
        return job

    @property
    def qargs(self):
        """
        :return: list of queue configuration arguments
        :rtype: list[str]
        """
        return self._qargs

    @property
    def bin(self):
        """
        :return: list of executable command chunks
        :rtype: list[str]
        """
        return self._bin

    @property
    def env(self):
        return self._env

    def get_options(self, values):
        """
        :return: list of command options
        :rtype: list[str]
        """
        options = [
            token
            for opt in filter(
                None,
                (
                    option.get_cmd_option(values.get(option.name))
                    for option in self._options
                )
            )
            for token in shlex.split(opt)
        ]
        return options

    @property
    def file_results(self):
        return self._file_results

    def submit(self, values, cwd):
        """
        Submits the job with given options
        """
        raise NotImplementedError

    @staticmethod
    def make_from_conf(conf):
        """
        :param conf: configuration dictionary grabbed from the config file
        :return: dictionary of executors for each configuration
        :rtype: dict[str, Executor]
        """
        options = [
            CommandOption(
                name=option['ref'],
                param=option['param'],
                default=option.get('val')
            )
            for option in conf.get('options', [])
        ]
        file_results = []
        for res in conf.get('result', []):
            if "path" in res:
                file_results.append(FileResult(res['path']))
            elif "pattern" in res:
                file_results.append(PatternFileResult(res['pattern']))
            else:
                raise ValueError("No property \"pattern\" or \"path\"")
        executors = {}
        for name, configuration in conf.get('configurations', {}).items():
            cls = getattr(
                sys.modules[__name__], configuration['execClass']
            )
            executors[name] = cls(
                bin=configuration['bin'],
                options=options,
                qargs=configuration.get('queueArgs'),
                file_results=file_results,
                env=configuration.get('env')
            )
        return executors


# noinspection PyAbstractClass
class Job(JobMixin):

    def __init__(self, job_id, cwd, executor):
        self.id = job_id
        self._cwd = cwd
        self._file_results = executor.file_results

    @property
    def status(self):
        return self.get_status(self.id)

    @property
    def result(self):
        return self.get_result(self.id)

    @property
    def cwd(self):
        return self._cwd

    @property
    def file_results(self):
        return [
            path
            for file_result in self._file_results
            for path in file_result.get_paths(self.cwd)
        ]

    def is_finished(self):
        return self.status in {
            Job.STATUS_SUCCESS, Job.STATUS_FAILED, Job.STATUS_EXCEPTION
        }

    def __repr__(self):
        return "<Job %d>" % self.id


class JobOutput:
    __slots__ = ['return_code', 'stdout', 'stderr']

    def __init__(self, return_code, stdout, stderr):
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr

    def __repr__(self):
        return (
            "<JobOutput rcode=%d stdout=%s stderr=%s>" %
            (self.return_code, self.stdout, self.stderr)
        )


class ShellExec(Executor):

    def submit(self, values, cwd):
        options = self.get_options(values)
        command = self.bin + options
        return subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            universal_newlines=True
        )

    def get_status(self, process):
        """
        :type process: subprocess.Popen
        """
        status = process.poll()
        if status is None:
            return self.STATUS_RUNNING
        if status == 0:
            return self.STATUS_SUCCESS
        else:
            return self.STATUS_FAILED

    def get_result(self, process):
        """
        :type process: subprocess.Popen
        """
        stdout, stderr = process.communicate()
        return JobOutput(
            return_code=process.returncode,
            stdout=stdout,
            stderr=stderr
        )


class LocalExec(Executor):

    def submit(self, values, cwd):
        command = self.bin + self.get_options(values)
        return QueueServer.submit_job(command, cwd, self.env)

    def get_status(self, job_id):
        return QueueServer.get_job_status(job_id)

    def get_result(self, job_id):
        return JobOutput(*QueueServer.get_job_output(job_id))


class ClusterExec(Executor):

    def submit(self, values, cwd):
        pass

    def get_status(self, job_id):
        pass

    def get_result(self, job_id):
        pass
