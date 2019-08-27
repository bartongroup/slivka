import asyncio
import itertools
import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from collections import namedtuple
from datetime import datetime
from itertools import islice
from typing import Iterator, List, Iterable, Tuple

import pkg_resources

import slivka
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


class Runner:
    _envvar_regex = re.compile(
        r'\$(?:(\$)|([_a-z]\w*)|{([_a-z]\w*)})',
        re.UNICODE | re.IGNORECASE
    )
    _name_generator = ('runner-%d' % i for i in itertools.count(1))
    JOBS_DIR = None

    def __init__(self, command_def, name=None):
        if self.JOBS_DIR is None:
            Runner.JOBS_DIR = slivka.settings.JOBS_DIR
        self.name = name or next(self._name_generator)
        self.inputs = command_def['inputs']
        self.outputs = command_def['outputs']
        self.env = {
            'PATH': os.getenv('PATH'),
            'SLIVKA_HOME': os.getenv('SLIVKA_HOME', os.getcwd())
        }
        self.env.update(command_def.get('env', {}))
        base_command = command_def['baseCommand']
        if isinstance(base_command, str):
            base_command = shlex.split(base_command)
        self.base_command = [
            self._envvar_regex.sub(self._replace_env_var, arg)
            for arg in base_command
        ]
        arguments = command_def.get('arguments', [])
        self.arguments = [
            self._envvar_regex.sub(self._replace_env_var, arg)
            for arg in arguments
        ]

    def _replace_env_var(self, match):
        if match.group(1):
            return '$'
        else:
            return self.env.get(match.group(2) or match.group(3))

    def get_args(self, values) -> List[str]:
        args = []
        for name, inp in self.inputs.items():
            value = values.get(name, inp.get('value'))
            if value is None or value is False:
                continue
            param_type = inp.get('type', 'string')
            if param_type == 'flag':
                value = 'true' if value else ''
            elif param_type == 'number':
                value = str(value)
            elif param_type == 'file':
                value = inp.get('symlink', value)
            param = self._envvar_regex.sub(self._replace_env_var, inp['arg'])
            param = str.replace(param, '$(value)', shlex.quote(value))
            args.extend(shlex.split(param))
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
        return RunInfo(cwd=cwd, id=self.submit(cmd, cwd))

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
        for i, cmd, cwd in zip(itertools.count(1), cmds, cwds):
            log.info('%s batch submitting command %s %s (%d/%d)',
                     self.__class__.__name__, cmd, cwd, i, len(cmds))
        job_ids = self.batch_submit(zip(cmds, cwds))
        return map(RunInfo._make, zip(job_ids, cwds))

    def submit(self, cmd, cwd):
        raise NotImplementedError

    def batch_submit(self, commands) -> Iterable:
        return (self.submit(cmd, cwd) for cmd, cwd in commands)

    @classmethod
    def check_status(cls, job_id) -> JobStatus:
        raise NotImplementedError

    @classmethod
    def batch_check_status(cls, job_ids) -> Iterable[JobStatus]:
        return map(cls.check_status, job_ids)

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
    def check_status(cls, pid):
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
    def check_status(cls, identifier):
        response = cls.client.get_job_status(identifier)
        return response.status


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
            self[key] = JobStatus.UNDEFINED
            return JobStatus.UNDEFINED

    _status_letters = StatusLetterDict({
        b'r': JobStatus.RUNNING,
        b't': JobStatus.RUNNING,
        b's': JobStatus.RUNNING,
        b'qw': JobStatus.QUEUED,
        b'T': JobStatus.QUEUED,
        b'd': JobStatus.DELETED,
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
        old_loop = asyncio.get_event_loop()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ids = []
        try:
            for slice in iter(lambda: list(islice(commands, self.QSUB_LIMIT)), []):
                coros = [self.async_submit(cmd, cwd) for cmd, cwd in slice]
                ids.extend(loop.run_until_complete(asyncio.gather(*coros)))
        finally:
            loop.close()
            asyncio.set_event_loop(old_loop)
        return ids

    @classmethod
    def check_status(cls, job_id):
        raise NotImplementedError

    @classmethod
    def batch_check_status(cls, job_ids):
        stdout = subprocess.check_output('qstat')
        stats = {}
        matches = cls._job_status_regex.findall(stdout)
        for job_id, status in matches:
            stats[job_id] = cls._status_letters[status]
        return (stats.get(job_id, JobStatus.COMPLETED) for job_id in job_ids)
