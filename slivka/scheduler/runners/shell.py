import contextlib
import logging
import os
import subprocess
from typing import List

from slivka import JobStatus
from ..runner import Command, Job, BaseCommandRunner

log = logging.getLogger('slivka.scheduler')


class ShellRunner(BaseCommandRunner):
    """ Implementation of the :py:class:`Runner` for shell.

    This is the most primitive approach that runs the job
    in a new shell process. Useful, if you are handling
    very few jobs and want to run them on the same system as
    the server with minimal overhead and no queueing system.

    The number of processes running simultaneously is not controlled
    so care must be taken not to exhaust all system resources.

    If the scheduler is restarted, the process handles are lost.
    """
    procs = {}

    def start_one(self, command: Command) -> Job:
        """ Starts the job as a subprocess. """
        proc = subprocess.Popen(
            command.args,
            stdout=open(os.path.join(command.cwd, 'stdout'), 'wb'),
            stderr=open(os.path.join(command.cwd, 'stderr'), 'wb'),
            cwd=command.cwd,
            env=command.env,
            shell=True
        )
        self.procs[proc.pid] = proc
        return Job(proc.pid, command.cwd)

    def start(self, commands: List[Command]) -> List[Job]:
        return list(map(self.start_one, commands))

    def status_one(self, job: Job) -> JobStatus:
        try:
            return_code = self.procs[job.id].poll()
        except KeyError:
            return JobStatus.INTERRUPTED
        if return_code is None:
            return JobStatus.RUNNING
        if return_code == 0:
            return JobStatus.COMPLETED
        if return_code == 127:
            return JobStatus.ERROR
        if return_code > 0:
            return JobStatus.FAILED
        if return_code < 0:
            return JobStatus.INTERRUPTED

    def status(self, jobs: List[Job]) -> List[JobStatus]:
        return list(map(self.status_one, jobs))

    def cancel_one(self, job: Job):
        with contextlib.suppress(OSError, KeyError):
            self.procs[job.id].terminate()

    def cancel(self, jobs: List[Job]):
        for job in jobs:
            self.cancel_one(job)
