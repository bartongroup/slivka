import functools
import logging
import shlex

import slivka.conf
from slivka import JobStatus
from slivka.local_queue import LocalQueueClient
from . import Command
from .runner import Runner, Job

log = logging.getLogger('slivka.scheduler')


@functools.lru_cache(maxsize=32)
def _get_client(address):
    return LocalQueueClient(address)


class SlivkaQueueRunner(Runner):
    """ Implementation of the :py:class:`Runner` for Slivka workers.

    This runner delegates the job execution the the slivka's
    simple queuing system running as a separate process.
    It has an advantage of running jobs on a separate system/node,
    controlling the number of simultaneous jobs and preserving jobs
    between scheduler restarts.
    """
    def __init__(self, *args, address=None, **kwargs):
        super().__init__(*args, **kwargs)
        if address is None:
            address = slivka.conf.settings.local_queue.host
        self.client = _get_client(address)

    def submit(self, command: Command) -> Job:
        response = self.client.submit_job(
            cmd=str.join(' ', map(shlex.quote, command.args)),
            cwd=command.cwd,
            env=self.env
        )
        return Job(response.id, command.cwd)

    def check_status(self, job: Job) -> JobStatus:
        response = self.client.get_job_status(job.id)
        return JobStatus(response.state)

    def cancel(self, job: Job):
        self.client.cancel_job(job.id)
