import atexit
import logging
import os
import re
import shlex
import subprocess
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Sequence, Collection

import pkg_resources

from slivka import JobStatus
from slivka.utils import ttl_cache
from .runner import Runner, Job, Command

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


@ttl_cache(ttl=5)
def _job_stat():
    stdout = subprocess.check_output('qstat')
    return {
        jid: _status_letters[letter]
        for jid, letter in _job_status_regex.findall(stdout)
    }


class GridEngineRunner(Runner):
    """ Implementation of the :py:class:`Runner` for Univa Grid Engine.

    This runner submits jobs to the Univa Grid Engine using ``qsub``
    command. Useful for more advanced systems dealing with high
    load that needs to distribute computationally heavy jobs
    and have high control over the resources used by each job.
    """
    finished_job_timestamp = defaultdict(datetime.now)

    def __init__(self, *args, qargs=(), **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(qargs, str):
            qargs = shlex.split(qargs)
        self.qsub_args = qargs
        self.env.update(
            (env, os.getenv(env)) for env in os.environ
            if env.startswith('SGE')
        )

    def submit(self, command: Command) -> Job:
        """
        Creates a temporary script file containing the command to
        execute and runs it with qsub. The output and error streams
        are written to the stdout and stderr files in the job working
        directory.
        """
        fd, path = tempfile.mkstemp(prefix='run', suffix='.sh', dir=command.cwd)
        cmd = str.join(' ', map(shlex.quote, command.args))
        with open(fd, 'w') as f:
            f.write(_runner_sh_tpl.format(cmd=cmd))
        # TODO: add -terse argument for job id only
        qsub_cmd = ['qsub', '-V', '-cwd', '-o', 'stdout', '-e', 'stderr',
                    *self.qsub_args, path]
        proc = subprocess.run(
            qsub_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=command.cwd,
            env=self.env,
            universal_newlines=False
        )
        proc.check_returncode()
        match = _job_submitted_regex.match(proc.stdout)
        return Job(match.group(1), command.cwd)

    def batch_submit(self, commands: Sequence[Command]) -> Sequence[Job]:
        """
        Batch submit is performed by repeated calls to
        :py:meth:`submit`. The thread pool executor ensures that
        the limit of subprocesses is not be exceeded.

        :param commands: iterable of args list and cwd path pairs
        :return: list of identifiers
        """
        return list(_executor.map(self.submit, commands))

    def check_status(self, job: Job) -> JobStatus:
        # there is no single job status check
        return self.batch_check_status([job])[0]

    def batch_check_status(self, jobs: Sequence[Job]) -> Sequence[JobStatus]:
        states = _job_stat()
        result = []
        for job in jobs:
            state = states.get(job.id)
            if state is not None:
                result.append(state)
            else:
                fn = os.path.join(job.cwd, 'finished')
                try:
                    with open(fn) as fp:
                        return_code = int(fp.read())
                    self.finished_job_timestamp.pop(job.id, None)
                    result.append(
                        JobStatus.COMPLETED if return_code == 0 else
                        JobStatus.ERROR if return_code == 127 else
                        JobStatus.FAILED
                    )
                except FileNotFoundError:
                    # one minute window for file system synchronization
                    ts = self.finished_job_timestamp[job.id]
                    if datetime.now() - ts < timedelta(minutes=1):
                        result.append(JobStatus.RUNNING)
                    else:
                        del self.finished_job_timestamp[job.id]
                        result.append(JobStatus.INTERRUPTED)
        return result

    def cancel(self, job: Job):
        subprocess.run([b'qdel', job.id])

    def batch_cancel(self, jobs: Collection[Job]):
        subprocess.run([b'qdel', *(job.id for job in jobs)])
