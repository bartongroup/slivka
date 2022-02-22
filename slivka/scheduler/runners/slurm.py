import logging
import os
import pwd
import re
import shlex
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Sequence

import pkg_resources

from slivka import JobStatus
from slivka.utils import ttl_cache
from .grid_engine import _StatusLetterDict
from .runner import Runner, Job, Command

log = logging.getLogger("slivka.scheduler")

_runner_sh_tpl = pkg_resources.resource_string(__name__, "runner.sh.tpl").decode()


_status_letters = _StatusLetterDict({
    'BF': JobStatus.ERROR,
    'CA': JobStatus.INTERRUPTED,
    'CD': JobStatus.COMPLETED,
    'CF': JobStatus.QUEUED,
    'CG': JobStatus.RUNNING,
    'DL': JobStatus.DELETED,
    'F': JobStatus.FAILED,
    'NF': JobStatus.ERROR,
    'OOM': JobStatus.ERROR,
    'PD': JobStatus.QUEUED,
    'PR': JobStatus.DELETED,
    'R': JobStatus.RUNNING,
    'RD': JobStatus.QUEUED,
    'RF': JobStatus.QUEUED,
    'RH': JobStatus.QUEUED,
    'RQ': JobStatus.QUEUED,
    'RS': JobStatus.QUEUED,
    # 'RV': JobStatus.UNKNOWN,
    'SI': JobStatus.CANCELLING,  # not sure
    # 'SE': JobStatus.UNKNOWN,
    # 'SO': JobStatus.UNKNOWN,
    'ST': JobStatus.INTERRUPTED,
    'S': JobStatus.QUEUED,
    'TO': JobStatus.INTERRUPTED
})

username = pwd.getpwuid(os.getuid()).pw_name


@ttl_cache(ttl=5)
def _job_stat():
    stdout = subprocess.check_output(
        ['squeue', '--array', '--format=%i %t', '--noheader', '--states=all',
         '--user=%s' % username],
        encoding='ascii'
    )
    return {
        jid: _status_letters[letter]
        for jid, letter in re.findall(r'^(\w+) ([A-Z]+)$', stdout, re.MULTILINE)
    }


class SlurmRunner(Runner):
    finished_job_timestamp = defaultdict(datetime.now)

    def __init__(self, *args, sbatchargs=(), **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(sbatchargs, str):
            sbatchargs = shlex.split(sbatchargs)
        self.sbatch_args = sbatchargs
        self.env.update(
            (env, os.getenv(env)) for env in os.environ
            if env.startswith("SLURM")
        )

    def submit(self, command: Command) -> Job:
        cmd = str.join(' ', map(shlex.quote, command.args))
        input_script = _runner_sh_tpl.format(cmd=cmd)
        proc = subprocess.run(
            ['sbatch', '--output=stdout', '--error=stderr', '--parsable',
             *self.sbatch_args],
            input=input_script,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=command.cwd,
            env=self.env,
            encoding='ascii'
        )
        proc.check_returncode()
        match = re.match(r'^(\w+)', proc.stdout)
        return Job(match.group(0), command.cwd)

    def batch_submit(self, commands: Sequence[Command]) -> Sequence[Job]:
        return list(map(self.submit, commands))

    def check_status(self, job: Job) -> JobStatus:
        return self.batch_check_status([job])[0]

    def batch_check_status(self, jobs: Sequence[Job]) -> Sequence[JobStatus]:
        statuses = _job_stat()
        result = []
        for job in jobs:
            status = statuses.get(job.id)
            if status is None or status == JobStatus.COMPLETED:
                fn = os.path.join(job.cwd, 'finished')
                try:
                    with open(fn) as fp:
                        return_code = int(fp.read())
                    self.finished_job_timestamp.pop(job.id, None)
                    status = (
                        JobStatus.COMPLETED if return_code == 0 else
                        JobStatus.ERROR if return_code == 127 else
                        JobStatus.INTERRUPTED if return_code >= 128 else
                        JobStatus.INTERRUPTED if return_code < 0 else
                        JobStatus.FAILED
                    )
                except FileNotFoundError:
                    ts = self.finished_job_timestamp[job.id]
                    if datetime.now() - ts < timedelta(minutes=1):
                        status = JobStatus.RUNNING
                    else:
                        del self.finished_job_timestamp[job.id]
                        status = JobStatus.INTERRUPTED
            result.append(status)
        return result

    def cancel(self, job: Job):
        subprocess.run(['scancel', job.id])

    def batch_cancel(self, jobs: Sequence[Job]):
        subprocess.run(['scancel', *(job.id for job in jobs)])
