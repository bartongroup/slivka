import contextlib
import logging
import os
import subprocess

from slivka import JobStatus
from .runner import Runner, Command, Job

log = logging.getLogger('slivka.scheduler')


class ShellRunner(Runner):
    """ Implementation of the :py:class:`Runner` using subprocesses.

    This is the most primitive approach that runs the job
    as a subprocess. Useful, if you are handling
    very few jobs and want to run them on the same system as
    the scheduler with minimal overhead and no queueing system.

    The number of processes running simultaneously is not controlled
    so care must be taken not to exhaust all system resources.

    If the scheduler is restarted, the process handles are lost.
    """
    procs = {}

    def submit(self, command: Command) -> Job:
        """ Starts the job as a subprocess. """
        proc = subprocess.Popen(
            command.args,
            stdout=open(os.path.join(command.cwd, 'stdout'), 'wb'),
            stderr=open(os.path.join(command.cwd, 'stderr'), 'wb'),
            cwd=command.cwd,
            env=self.env,
            shell=False
        )
        self.procs[proc.pid] = proc
        return Job(proc.pid, command.cwd)

    def check_status(self, job: Job) -> JobStatus:
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

    def cancel(self, job: Job):
        with contextlib.suppress(OSError, KeyError):
            self.procs[job.id].terminate()
