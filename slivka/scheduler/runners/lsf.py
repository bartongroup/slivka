import logging
import os
import pwd
import re
import shlex
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Sequence

from slivka import JobStatus
from slivka.compat import resources
from slivka.utils import ttl_cache
from ._bash_lex import bash_quote
from .grid_engine import _StatusLetterDict
from .runner import Runner, Job, Command

log = logging.getLogger("slivka.scheduler")

_runner_bash_tpl = resources.read_text(__name__, "lsf-runner.bash.tpl")


_status_letters = _StatusLetterDict({
    'PEND': JobStatus.QUEUED,
    'PROV': JobStatus.QUEUED,
    'PSUSP': JobStatus.UNKNOWN,
    'RUN': JobStatus.RUNNING,
    'USUSP': JobStatus.UNKNOWN,
    'SSUSP': JobStatus.UNKNOWN,
    'DONE': JobStatus.COMPLETED,
    'EXIT': JobStatus.ERROR,
    'UNKWN': JobStatus.UNKNOWN,
    'WAIT': JobStatus.QUEUED,
    'ZOMBI': JobStatus.ERROR
})

@ttl_cache(ttl=5)
def _job_stat():
    stdout = subprocess.check_output(
        ['bjobs', '-noheader', '-w'],
        encoding='ascii'
    )
    return {
        jid: _status_letters[letter]
        for jid, letter in re.findall(r'^(\w+)\s+\w+\s+([A-Z]+)', stdout, re.MULTILINE)
    }


class LSFRunner(Runner):
    finished_job_timestamp = defaultdict(datetime.now)

    def __init__(self, *args, bsubargs=(), **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(bsubargs, str):
            bsubargs = shlex.split(bsubargs)
        self.bsub_args = bsubargs
        self.env.update(
            (env, os.getenv(env)) for env in os.environ
            if env.startswith("LSF") or env.startswith("LSB")
        )

    def submit(self, command: Command) -> Job:
        cmd = str.join(' ', map(bash_quote, command.args))
        input_script = _runner_bash_tpl.format(cmd=cmd)
        proc = subprocess.run(
            # NB unlike other runners, the "stdout" file gets redirected by the job
            # script because LSF normally writes a "job report" to stdout, and there
            # isn't a general and reliable way to suppress this as far as I can tell
            # (see also https://stackoverflow.com/questions/9038314/can-i-suppress-an-lsf-job-report-without-sending-mail)
            # so the "-o" here *just* sends the job report to its own file.  In future
            # we could possibly switch to "-o /dev/null" if we decide we don't want
            # the job report at all.
            ['bsub', '-o', 'stdout.lsf', '-e', 'stderr',
             *self.bsub_args],
            input=input_script,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=command.cwd,
            env=self.env,
            encoding='ascii'
        )
        proc.check_returncode()
        match = re.match(r'^Job <(\d+)>', proc.stdout)
        return Job(match.group(1), command.cwd)

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
        subprocess.run(['bkill', job.id])

    def batch_cancel(self, jobs: Sequence[Job]):
        subprocess.run(['bkill', *(job.id for job in jobs)])
