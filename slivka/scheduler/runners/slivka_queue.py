import functools
import logging
import shlex
from typing import List

import slivka.conf
from slivka import JobStatus
from slivka.local_queue import LocalQueueClient
from ..runner import BaseCommandRunner, Job, Command

log = logging.getLogger('slivka.scheduler')


@functools.lru_cache(maxsize=32)
def _get_client(address):
    return LocalQueueClient(address)


class SlivkaQueueRunner(BaseCommandRunner):
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

    def start_one(self, command: Command) -> Job:
        response = self.client.submit_job(
            cmd=str.join(' ', map(shlex.quote, command.args)),
            cwd=command.cwd,
            env=command.env
        )
        return Job(response.id, command.cwd)

    def start(self, commands: List[Command]) -> List[Job]:
        return list(map(self.start_one, commands))

    def status_one(self, job: Job) -> JobStatus:
        response = self.client.get_job_status(job.id)
        return JobStatus(response.state)

    def status(self, jobs: List[Job]) -> List[JobStatus]:
        return list(map(self.status_one, jobs))

    def cancel_one(self, job: Job):
        self.client.cancel_job(job.id)

    def cancel(self, jobs: List[Job]):
        for job in jobs:
            self.cancel_one(job)
