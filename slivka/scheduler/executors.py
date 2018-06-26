import getpass
import logging
import os
import pydoc
import re
import shlex
import subprocess
import sys
import uuid

import slivka
from slivka.scheduler.command import CommandOption, PathWrapper, \
    PatternPathWrapper
from slivka.scheduler.exceptions import QueueBrokenError, QueueError, \
    QueueUnavailableError, JobNotFoundError
from slivka.scheduler.task_queue import QueueServer

logger = logging.getLogger('slivka.scheduler.scheduler')


class Executor:

    # noinspection PyShadowingBuiltins
    def __init__(self, *, bin="", options=None, qargs=None, result_paths=None,
                 log_paths=None, env=None):
        """
        :param log_paths:
        :param bin: executable command
        :type bin: str
        :param options: list of command options
        :type options: list[CommandOption]
        :param qargs: queue engine arguments
        :type qargs: list[str]
        :param result_paths: list of result file path wrappers
        :type result_paths: list[PathWrapper]
        :param log_paths: list of log file path wrappers
        :type log_paths: list[PathWrapper]
        :param env: dictionary of environment variables to use
        :type env: dict[str, str]
        """
        self._qargs = qargs or []
        self._bin = shlex.split(bin)
        self._options = options or []
        self._result_paths = result_paths or []
        self._log_paths = log_paths or []
        self._env = env or {}

    def __call__(self, values):
        """Launch the new job.

        Creates a current working directory for the new job and issues the
        submit command which launches the job. Parameter ``values`` is a
        dictionary mapping the form field names to their values.
        Returns the Job instance for the future reference to that job.

        :param values: dict mapping field names to their values
        :return: job handler
        :rtype: Job
        """
        cwd = os.path.join(slivka.settings.WORK_DIR, uuid.uuid4().hex)
        os.mkdir(cwd)
        try:
            job_id = self.submit(values, cwd)
        except QueueError:
            raise
        except Exception:
            logger.critical("Critical error occurred when submitting the job",
                            exc_info=True)
            raise QueueBrokenError
        job_wrapper_class = self.get_job_wrapper_class()
        job_wrapper = job_wrapper_class(job_id, cwd, self)
        return job_wrapper

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
        """
        :return: environment variables
        :rtype: dict[str, str]
        """
        return self._env

    def get_options(self, values):
        """Fill command option templates and concatenate them.

        For each option picks the corresponding value and inserts into template.
        Then, options are concatenated into the list of command line arguments.

        :return: list of command arguments
        :rtype: list[str]
        """
        options = [
            token
            for opt in (
                option.get_cmd_option(values.get(option.name))
                for option in self._options
            )
            if opt is not None
            for token in shlex.split(opt)
        ]
        return options

    @property
    def result_paths(self):
        return self._result_paths

    @property
    def log_paths(self):
        return self._log_paths

    def submit(self, values, cwd):
        """Submit the job with given options."""
        raise NotImplementedError

    @staticmethod
    def get_job_wrapper_class():
        """Get the job class used by this executor.

        :return: Class of the associated job
        """
        raise NotImplementedError

    @staticmethod
    def make_from_conf(conf):
        """
        :param conf: configuration dictionary grabbed from the config file
        :return: dictionary of executors for each configuration
        :rtype: (dict[str, Executor], JobLimits)
        """
        options = Executor._make_option_templates(conf.get('options', []))
        (result_wrappers, log_wrappers) = (
            Executor._make_output_file_wrappers(conf.get('result', []))
        )
        executors = {}
        for name, configuration in conf.get('configurations', {}).items():
            executor_class = getattr(
                sys.modules[__name__], configuration['execClass']
            )
            executors[name] = executor_class(
                bin=configuration['bin'],
                options=options,
                qargs=configuration.get('queueArgs'),
                result_paths=result_wrappers,
                log_paths=log_wrappers,
                env=configuration.get('env')
            )

        limits = pydoc.locate(conf['limits'], forceload=1)
        if limits is None:
            raise ImportError(conf['limits'])
        return executors, limits

    @staticmethod
    def _make_option_templates(options):
        return [
            CommandOption(
                name=option['ref'],
                param=option['param'],
                default=option.get('val')
            )
            for option in options
        ]

    @staticmethod
    def _make_output_file_wrappers(outputs):
        result_wrappers = []
        log_wrappers = []
        for result in outputs:
            if "path" in result:
                wrapper = PathWrapper(result['path'])
            elif "pattern" in result:
                wrapper = PatternPathWrapper(result['pattern'])
            else:
                assert False, "\"pattern\" or \"path\" missing"
            if result['type'] == 'result':
                result_wrappers.append(wrapper)
            elif result['type'] == 'log' or result['type'] == 'error':
                log_wrappers.append(wrapper)
            else:
                raise ValueError("Invalid output type: \"%s\"" % result['type'])
        return result_wrappers, log_wrappers


class Job:

    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_DELETED = 'deleted'
    STATUS_FAILED = 'failed'
    STATUS_ERROR = 'error'

    def __init__(self, job_id, cwd, executor):
        """
        :param job_id:
        :param cwd:
        :param executor:
        :type executor: Executor
        """
        self._id = job_id
        self._cwd = cwd
        self._result_paths = executor.result_paths
        self._log_paths = executor.log_paths
        self._cached_status = None

    @property
    def id(self):
        return self._id

    @property
    def cached_status(self):
        if self._cached_status is None:
            return self.status
        else:
            return self._cached_status

    @property
    def status(self):
        try:
            self._cached_status = self.get_status(self.id)
            return self._cached_status
        except QueueError:
            self._cached_status = self.STATUS_ERROR
            raise
        except Exception:
            self._cached_status = self.STATUS_ERROR
            logger.critical(
                "Critical error occurred when retrieving job status",
                exc_info=True
            )
            raise QueueBrokenError

    @property
    def return_code(self):
        if self.cached_status in {Job.STATUS_QUEUED, Job.STATUS_RUNNING}:
            return None
        try:
            return self.get_result(self.id)
        except QueueError:
            raise
        except Exception:
            logger.critical(
                "Critical error occurred when retrieving job result",
                exc_info=True
            )
            raise QueueBrokenError

    @property
    def cwd(self):
        return self._cwd

    @property
    def result_paths(self):
        return [
            path
            for path_wrapper in self._result_paths
            for path in path_wrapper.get_paths(self.cwd)
        ]

    @property
    def log_paths(self):
        return [
            path
            for path_wrapper in self._log_paths
            for path in path_wrapper.get_paths(self.cwd)
        ]

    def get_status(self, job_id):
        """Return the completion status of the job.

        This method should be overridden in all ``Job`` subclasses to check
        the job status in a way specific to the execution method.
        It returns one of the status constants specified in the class fields.

        :param job_id: unique identifier allowing to recognise the job.
        """
        raise NotImplementedError

    def get_result(self, job_id):
        raise NotImplementedError

    def is_finished(self):
        return self.status not in {Job.STATUS_QUEUED, Job.STATUS_RUNNING}


class JobLimits:

    configurations = []

    # todo: rename to `select_configuration`
    def get_conf(self, fields):
        # noinspection PyBroadException
        try:
            self.setup(fields)
        except Exception:
            logger.critical(
                'Failed to setup configuration checker',
                exc_info=True
            )
            return None
        for conf in self.configurations:
            limit_check = getattr(self, "limit_%s" % conf, None)
            # noinspection PyBroadException
            try:
                if limit_check(fields):
                    return conf
            except Exception:
                logger.critical(
                    'Limit check for configuration %s raised exception',
                    conf,
                    exc_info=True
                )
        else:
            return None

    def setup(self, values):
        pass


class ShellExec(Executor):

    def submit(self, values, cwd):
        options = self.get_options(values)
        command = self.bin + options
        return subprocess.Popen(
            command,
            stdout=open(os.path.join(cwd, 'stdout.txt'), 'w'),
            stderr=open(os.path.join(cwd, 'stderr.txt'), 'w'),
            cwd=cwd,
            universal_newlines=True
        )

    @staticmethod
    def get_job_wrapper_class():
        return ShellJob


class ShellJob(Job):

    def get_status(self, process):
        """
        :type process: subprocess.Popen
        """
        if isinstance(process, str):
            return self.STATUS_FAILED
        try:
            status = process.poll()
        except OSError:
            raise QueueBrokenError
        except AttributeError:
            raise JobNotFoundError
        if status is None:
            return self.STATUS_RUNNING
        elif status == 0:
            return self.STATUS_COMPLETED
        else:
            return self.STATUS_FAILED

    def get_result(self, process):
        """
        :type process: subprocess.Popen
        """
        process.wait()
        return process.returncode


class LocalExec(Executor):

    def submit(self, values, cwd):
        command = self.bin + self.get_options(values)
        try:
            return QueueServer.submit_job(command, cwd, self.env)
        except ConnectionError:
            raise QueueUnavailableError

    @staticmethod
    def get_job_wrapper_class():
        return LocalJob


class LocalJob(Job):

    def get_status(self, job_id):
        try:
            return QueueServer.get_job_status(job_id)
        except ConnectionError:
            raise QueueUnavailableError

    def get_result(self, job_id):
        try:
            return QueueServer.get_job_return_code(job_id)
        except ConnectionError:
            raise QueueUnavailableError


class GridEngineExec(Executor):

    job_submission_regex = re.compile(
        r'Your job (\d+) \(.+\) has been submitted'
    )

    def submit(self, values, cwd):
        queue_command = [
            'qsub', '-cwd', '-e', 'stderr.txt', '-o', 'stdout.txt'
        ] + self.qargs
        process = subprocess.Popen(
            queue_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            cwd=cwd,
            env=self.env,
            universal_newlines=True
        )
        command_chunks = self.bin + self.get_options(values)
        command = ' '.join(shlex.quote(s) for s in command_chunks)
        stdin = ("echo > started;\n"
                 "%s;\n"
                 "echo > finished;") % command
        stdout, stderr = process.communicate(stdin)
        match = self.job_submission_regex.match(stdout)
        return match.group(1)

    @staticmethod
    def get_job_wrapper_class():
        return GridEngineJob


class GridEngineJob(Job):

    job_status_regex_pattern = (
        r'^{0}\s+[\d\.]+\s+.*?\s+[\w-]+\s+(\w{{1,3}})\s+[\d/]+\s+[\d:]+\s+'
        r'[\w@\.-]*\s+\d+$'
    )

    def get_status(self, job_id):
        username = getpass.getuser()
        process = subprocess.Popen(
            "qstat -u '%s'" % (username or '*'),
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True
        )
        out, err = process.communicate()
        regex = self.job_status_regex_pattern.format(job_id)
        match = re.search(regex, out, re.MULTILINE)
        if match is None:
            try:
                time_started = os.path.getmtime(
                    os.path.join(self.cwd, 'started'))
            except FileNotFoundError:
                return self.STATUS_QUEUED
            try:
                time_finished = os.path.getmtime(
                    os.path.join(self.cwd, 'finished'))
            except FileNotFoundError:
                return self.STATUS_RUNNING
            else:
                if time_finished >= time_started:
                    return self.STATUS_COMPLETED
                else:
                    return self.STATUS_RUNNING
        else:
            status = match.group(1)
            if status == 'r' or status == 't':
                return self.STATUS_RUNNING
            elif status == 'qw' or status == 'T':
                return self.STATUS_QUEUED
            elif status == 'd':
                return self.STATUS_DELETED
            else:
                raise QueueUnavailableError

    def get_result(self, job_id):
        return 0
