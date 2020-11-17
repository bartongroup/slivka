import atexit
import logging
import os
import re
import shlex
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Tuple, List

import pkg_resources

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


_executor = ThreadPoolExecutor()
atexit.register(_executor.shutdown)


class GridEngineRunner(Runner):

    def __init__(self, command_def, id=None, qsub_args=()):
        super().__init__(command_def, id)
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

    def batch_submit(self, commands: Iterable[Tuple[List, str]]):
        """
        :param commands: iterable of args list and cwd path pairs
        :return: list of identifiers
        """
        def submit_wrapper(args): self.submit(*args)
        return list(_executor.map(submit_wrapper, commands))

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
                    yield (
                        JobStatus.COMPLETED if return_code == 0 else
                        JobStatus.ERROR if return_code == 127 else
                        JobStatus.FAILED
                    )
                except FileNotFoundError:
                    yield JobStatus.INTERRUPTED

    @classmethod
    def cancel(cls, job_id, cwd):
        subprocess.run([b'qdel', job_id])

    @classmethod
    def batch_cancel(cls, jobs: Iterable[JobMetadata]):
        subprocess.run([b'qdel', *(job['job_id'] for job in jobs)])
