import contextlib
import logging
import os

import subprocess

from slivka import JobStatus
from .runner import Runner


log = logging.getLogger('slivka.scheduler')


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

    @classmethod
    def cancel(cls, pid, cwd):
        with contextlib.suppress(OSError, KeyError):
            cls.procs[pid].terminate()
