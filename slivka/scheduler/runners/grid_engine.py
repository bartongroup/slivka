import asyncio
import logging
import os
import shlex
import tempfile

import pkg_resources
import re
import subprocess
from itertools import islice
from typing import Iterable, Tuple, List

from slivka import JobStatus
from slivka.db.documents import JobMetadata
from .runner import Runner

log = logging.getLogger('slivka.scheduler')

_job_submitted_regex = re.compile(
    rb'Your job (\d+) \(.+\) has been submitted'
)
_job_status_regex = re.compile(
    rb'^\s*(\d+)\s+\d+\.\d*\s+[\w-]+\s+[\w-]+\s+(\w+)',
    re.MULTILINE
)
_runner_sh_tpl = pkg_resources.resource_string(__name__, "runner.sh.tpl").decode()

QSUB_LIMIT = 100


class _StatusLetterDict(dict):
    def __missing__(self, key):
        logging.error('Status letter %s is undefined', key)
        self[key] = JobStatus.UNKNOWN
        return JobStatus.UNKNOWN


_status_letters = _StatusLetterDict({
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


class GridEngineRunner(Runner):

    def __init__(self, command_def, name=None, qsub_args=()):
        super().__init__(command_def, name)
        self.qsub_args = qsub_args
        self.env.update(
            (env, os.getenv(env)) for env in os.environ
            if env.startswith('SGE')
        )

    def submit(self, cmd, cwd):
        fd, path = tempfile.mkstemp(prefix='run', suffix='.sh', dir=cwd)
        cmd = str.join(' ', map(shlex.quote, cmd))
        with open(fd, 'w') as f:
            f.write(_runner_sh_tpl.format(cmd=cmd))
        qsub_cmd = ['qsub', '-V', '-cwd', '-o', 'stdout', '-e', 'stderr',
                    *self.qsub_args, path]
        proc = subprocess.run(
            qsub_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=self.env,
            universal_newlines=False
        )
        proc.check_returncode()
        match = _job_submitted_regex.match(proc.stdout)
        return match.group(1)

    async def async_submit(self, cmd, cwd):
        fd, path = tempfile.mkstemp(prefix='run_', suffix='.sh', dir=cwd)
        cmd = str.join(' ', map(shlex.quote, cmd))
        with open(fd, 'w') as f:
            f.write(_runner_sh_tpl.format(cmd=cmd))
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
        match = _job_submitted_regex.match(stdout)
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
            for slice in iter(lambda: list(islice(commands, QSUB_LIMIT)), []):
                coros = [self.async_submit(cmd, cwd) for cmd, cwd in slice]
                ids.extend(loop.run_until_complete(asyncio.gather(*coros)))
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        return ids

    @classmethod
    def check_status(cls, job_id, cwd):
        job = dict(job_id=job_id, work_dir=cwd)
        return next(cls.batch_check_status([job]))

    @classmethod
    def batch_check_status(cls, jobs):
        stdout = subprocess.check_output('qstat')
        states = {}
        matches = _job_status_regex.findall(stdout)
        for job_id, status in matches:
            states[job_id] = _status_letters[status]
        for job in jobs:
            state = states.get(job['job_id'])
            if state is not None:
                yield state
            else:
                fn = os.path.join(job['work_dir'], 'finished')
                try:
                    with open(fn) as fp:
                        return_code = int(fp.read())
                    yield JobStatus.FAILED if return_code else JobStatus.COMPLETED
                except FileNotFoundError:
                    yield JobStatus.INTERRUPTED

    @classmethod
    def cancel(cls, job_id, cwd):
        subprocess.run([b'qdel', job_id])

    @classmethod
    def batch_cancel(cls, jobs: Iterable[JobMetadata]):
        subprocess.run([b'qdel', *(job['job_id'] for job in jobs)])
