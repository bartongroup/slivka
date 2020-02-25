import logging
import shlex

import slivka
from slivka import JobStatus
from slivka.local_queue import LocalQueueClient
from .runner import Runner


log = logging.getLogger('slivka.scheduler')


class SlivkaQueueRunner(Runner):
    client = None  # type: LocalQueueClient

    def __init__(self, command_def, name=None):
        super().__init__(command_def, name)
        if self.client is None:
            SlivkaQueueRunner.client = LocalQueueClient(
                slivka.settings.slivka_queue_address
            )

    def submit(self, cmd, cwd):
        response = self.client.submit_job(
            cmd=str.join(' ', map(shlex.quote, cmd)),
            cwd=cwd,
            env=self.env
        )
        return response.id

    @classmethod
    def check_status(cls, identifier, cwd):
        response = cls.client.get_job_status(identifier)
        return JobStatus(response.state)

    @classmethod
    def cancel(cls, job_id, cwd):
        cls.client.cancel_job(job_id)
