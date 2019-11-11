import asyncio
import contextlib
import itertools
import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from collections import namedtuple, ChainMap
from datetime import datetime
from functools import partial
from itertools import islice
from typing import Iterator, List, Iterable, Tuple, Match

import pkg_resources

import slivka
from slivka.db.documents import JobMetadata
from slivka.local_queue import LocalQueueClient
from slivka.utils import JobStatus

__all__ = [
    'RunInfo',
    'Runner',
    'GridEngineRunner',
    'ShellRunner',
    'SlivkaQueueRunner'
]

log = logging.getLogger('slivka.scheduler')
log.setLevel(logging.DEBUG)

RunInfo = namedtuple('RunInfo', 'id, cwd')

_envvar_regex = re.compile(
    r'\$(?:(\$)|([_a-z]\w*)|{([_a-z]\w*)})',
    re.UNICODE | re.IGNORECASE
)


def _replace_from_env(env: dict, match: Match):
    if match.group(1):
        return '$'
    else:
        return env.get(match.group(2) or match.group(3))


class Runner:
    _name_generator = ('runner-%d' % i for i in itertools.count(1))
    JOBS_DIR = None

    def __init__(self, command_def, name=None):
        if self.JOBS_DIR is None:
            Runner.JOBS_DIR = slivka.settings.JOBS_DIR
        self.name = name or next(self._name_generator)
        self.inputs = command_def['inputs']
        self.outputs = command_def['outputs']
        self.env = env = {
            'PATH': os.getenv('PATH'),
            'SLIVKA_HOME': os.getenv('SLIVKA_HOME', os.getcwd())
        }
        env.update(command_def.get('env', {}))
        replace = partial(_replace_from_env, os.environ)
        for key, val in env.items():
            # noinspection PyTypeChecker
            env[key] = _envvar_regex.sub(replace, val)
        replace = partial(_replace_from_env, ChainMap(env, os.environ))
        base_command = command_def['baseCommand']  # type: List[str]
        if isinstance(base_command, str):
            base_command = shlex.split(base_command)
        # noinspection PyTypeChecker
        self.base_command = [
            _envvar_regex.sub(replace, arg)
            for arg in base_command
        ]
        arguments = command_def.get('arguments', [])
        # noinspection PyTypeChecker
        self.arguments = [
            _envvar_regex.sub(replace, arg)
            for arg in arguments
        ]

    def get_args(self, values) -> List[str]:
        replace = partial(_replace_from_env, self.env)
        args = []
        for name, inp in self.inputs.items():
            value = values.get(name)
            if value is None:
                value = inp.get('value')
            if value is None or value is False:
                continue
            # noinspection PyTypeChecker
            # fixme: no need to regex sub every time, move to __init__
            tpl = _envvar_regex.sub(replace, inp['arg'])
            param_type = inp.get('type', 'string')
            if param_type == 'flag':
                value = 'true' if value else ''
            elif param_type == 'number':
                value = str(value)
            elif param_type == 'file':
                value = inp.get('symlink', value)
            elif param_type == 'array':
                join = inp.get('join')
                if join is not None:
                    value = str.join(join, value)

            if isinstance(value, list):
                args.extend(
                    arg.replace('$(value)', val)
                    for val in value
                    for arg in shlex.split(tpl)
                )
            else:
                args.extend(
                    arg.replace('$(value)', value)
                    for arg in shlex.split(tpl)
                )
        args.extend(self.arguments)
        return args

    def run(self, inputs) -> RunInfo:
        cwd = tempfile.mkdtemp(
            prefix=datetime.now().strftime("%y%m%d"), dir=self.JOBS_DIR
        )
        for name, input_conf in self.inputs.items():
            if input_conf.get('type') == 'file' and 'symlink' in input_conf:
                src = inputs.get(name)
                if src is not None:
                    mklink(src, os.path.join(cwd, input_conf['symlink']))
        cmd = self.base_command + self.get_args(inputs)
        log.info('%s submitting single command %s %s',
                 self.__class__.__name__, cmd, cwd)
        try:
            return RunInfo(cwd=cwd, id=self.submit(cmd, cwd))
        except Exception:
            with contextlib.suppress(OSError):
                shutil.rmtree(cwd)
            raise

    def batch_run(self, inputs_list) -> Iterator[RunInfo]:
        cwds = [
            tempfile.mkdtemp(
                prefix=datetime.now().strftime("%y%m%d"), dir=self.JOBS_DIR
            )
            for _ in inputs_list
        ]
        cmds = []
        for cwd, inputs in zip(cwds, inputs_list):
            for name, input_conf in self.inputs.items():
                if input_conf.get('type') == 'file' and 'symlink' in input_conf:
                    src = inputs.get(name)
                    if src is not None:
                        mklink(src, os.path.join(cwd, input_conf['symlink']))
            cmd = self.base_command + self.get_args(inputs)
            cmds.append(cmd)
        if log.isEnabledFor(logging.INFO):
            for i, cmd, cwd in zip(itertools.count(1), cmds, cwds):
                log.info('%s batch submitting command %s %s (%d/%d)',
                         self.__class__.__name__, cmd, cwd, i, len(cmds))
        try:
            job_ids = self.batch_submit(zip(cmds, cwds))
            return map(RunInfo._make, zip(job_ids, cwds))
        except Exception:
            for cwd in cwds:
                with contextlib.suppress(OSError):
                    shutil.rmtree(cwd)
            raise

    def submit(self, cmd, cwd):
        """
        :param cmd: list of command line arguments
        :param cwd: current working directory for the job
        :return: json-serializable job id
        :raise SubmissionError: submission to the queue failed
        """
        raise NotImplementedError

    def batch_submit(self, commands: Iterable[Tuple[List[str], str]]) -> Iterable:
        """
        :param commands: iterable of command arguments and working directory pairs
        :return: iterable of json-serializable job ids
        :raise SubmissionError: submission to the queue failed
        """
        return [self.submit(cmd, cwd) for cmd, cwd in commands]

    @classmethod
    def check_status(cls, job_id, cwd) -> JobStatus:
        raise NotImplementedError

    @classmethod
    def batch_check_status(cls, jobs: Iterable[JobMetadata]) -> Iterable[JobStatus]:
        return [cls.check_status(job.job_id, job.work_dir) for job in jobs]

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.name)


def mklink(src, dst):
    try:
        os.symlink(src, dst)
    except OSError:
        try:
            os.link(src, dst)
        except OSError:
            shutil.copyfile(src, dst)


class ShellRunner(Runner):
    procs = {}

    def submit(self, cmd, cwd):
        proc = subprocess.Popen(
            cmd,
            stdout=open(os.path.join(cwd, 'stdout'), 'wb'),
            stderr=open(os.path.join(cwd, 'stderr'), 'wb'),
            cwd=cwd,
            env=self.env
        )
        self.procs[proc.pid] = proc
        return proc.pid

    @classmethod
    def check_status(cls, pid, cwd):
        try:
            return_code = cls.procs[pid].poll()
        except KeyError:
            return JobStatus.INTERRUPTED
        if return_code is None:
            return JobStatus.RUNNING
        if return_code == 0:
            return JobStatus.COMPLETED
        if return_code > 0:
            return JobStatus.FAILED
        if return_code < 0:
            return JobStatus.INTERRUPTED


class SlivkaQueueRunner(Runner):
    client = None

    def __init__(self, command_def, name=None):
        super().__init__(command_def, name)
        if self.client is None:
            SlivkaQueueRunner.client = LocalQueueClient(
                slivka.settings.SLIVKA_QUEUE_ADDR
            )

    def submit(self, cmd, cwd):
        response = self.client.submit_job(
            cmd=str.join(' ', map(shlex.quote, cmd)),
            cwd=cwd,
            env=self.env
        )
        return response.id

    @classmethod
    def check_status(cls, identifier, cwd):
        response = cls.client.get_job_status(identifier)
        return JobStatus(response.status)


class GridEngineRunner(Runner):
    _job_submitted_regex = re.compile(
        rb'Your job (\d+) \(.+\) has been submitted'
    )
    _job_status_regex = re.compile(
        rb'^\s*(\d+)\s+\d+\.\d*\s+[\w-]+\s+[\w-]+\s+(\w+)',
        re.MULTILINE
    )
    _runner_sh_tpl = pkg_resources.resource_string(__name__, "runner.sh.tpl").decode()
    QSUB_LIMIT = 100

    def __init__(self, command_def, name=None, qsub_args=()):
        super().__init__(command_def, name)
        self.qsub_args = qsub_args
        self.env.update(
            (env, os.getenv(env)) for env in os.environ
            if env.startswith('SGE')
        )

    class StatusLetterDict(dict):
        def __missing__(self, key):
            logging.error('Status letter %s is undefined', key)
            self[key] = JobStatus.UNKNOWN
            return JobStatus.UNKNOWN

    _status_letters = StatusLetterDict({
        b'r': JobStatus.RUNNING,
        b't': JobStatus.RUNNING,
        b's': JobStatus.RUNNING,
        b'qw': JobStatus.QUEUED,
        b'T': JobStatus.QUEUED,
        b'd': JobStatus.DELETED,
        b'dr': JobStatus.DELETED,
        b'E': JobStatus.ERROR,
        b'Eqw': JobStatus.ERROR
    })

    def submit(self, cmd, cwd):
        fd, path = tempfile.mkstemp(prefix='run', suffix='.sh', dir=cwd)
        cmd = str.join(' ', map(shlex.quote, cmd))
        with open(fd, 'w') as f:
            f.write(self._runner_sh_tpl.format(cmd=cmd))
        qsub_cmd = ['qsub', '-V', '-cwd', '-o', 'stdout', '-e', 'stderr',
                    *self.qsub_args, path]
        proc = subprocess.run(
            qsub_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=self.env,
            universal_newlines=True
        )
        proc.check_returncode()
        match = self._job_submitted_regex.match(proc.stdout)
        return match.group(1)

    async def async_submit(self, cmd, cwd):
        fd, path = tempfile.mkstemp(prefix='run_', suffix='.sh', dir=cwd)
        cmd = str.join(' ', map(shlex.quote, cmd))
        with open(fd, 'w') as f:
            f.write(self._runner_sh_tpl.format(cmd=cmd))
        args = ('-V', '-cwd', '-o', 'stdout', '-e', 'stderr', *self.qsub_args, path)
        proc = await asyncio.create_subprocess_exec(
            'qsub', *args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=self.env
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            log.error(
                "qsub exited with status code %d, stdout: '%s', stderr: '%s'",
                proc.returncode, stdout, stderr
            )
            raise subprocess.CalledProcessError(proc.returncode, ('qsub', *args))
        log.debug('qsub completed')
        match = self._job_submitted_regex.match(stdout)
        return match.group(1)

    def batch_submit(self, commands: Iterable[Tuple[List, str]]):
        """
        :param commands: iterable of args list and cwd path pairs
        :return: list of identifiers
        """
        commands = iter(commands)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ids = []
        try:
            for slice in iter(lambda: list(islice(commands, self.QSUB_LIMIT)), []):
                coros = [self.async_submit(cmd, cwd) for cmd, cwd in slice]
                ids.extend(loop.run_until_complete(asyncio.gather(*coros)))
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        return ids

    @classmethod
    def check_status(cls, job_id, cwd):
        raise NotImplementedError

    @classmethod
    def batch_check_status(cls, jobs):
        stdout = subprocess.check_output('qstat')
        states = {}
        matches = cls._job_status_regex.findall(stdout)
        for job_id, status in matches:
            states[job_id] = cls._status_letters[status]
        for job in jobs:
            state = states.get(job.job_id)
            if state is not None:
                yield state
            else:
                fn = os.path.join(job.work_dir, 'finished')
                try:
                    with open(fn) as fp:
                        return_code = int(fp.read())
                    yield JobStatus.FAILED if return_code else JobStatus.COMPLETED
                except FileNotFoundError:
                    yield JobStatus.INTERRUPTED
