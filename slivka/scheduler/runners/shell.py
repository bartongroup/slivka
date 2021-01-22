import contextlib
import logging
import os
import subprocess

from slivka import JobStatus
from .runner import Runner

log = logging.getLogger('slivka.scheduler')


class ShellRunner(Runner):
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

    def submit(self, cmd, cwd):
        """ Starts the job as a subprocess. """
        proc = subprocess.Popen(
            cmd,
            stdout=open(os.path.join(cwd, 'stdout'), 'wb'),
            stderr=open(os.path.join(cwd, 'stderr'), 'wb'),
            cwd=cwd,
            env=self.env,
            shell=True
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
        if return_code == 127:
            return JobStatus.ERROR
        if return_code > 0:
            return JobStatus.FAILED
        if return_code < 0:
            return JobStatus.INTERRUPTED

    @classmethod
    def cancel(cls, pid, cwd):
        with contextlib.suppress(OSError, KeyError):
            cls.procs[pid].terminate()
