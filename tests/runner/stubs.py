import tempfile

from slivka import JobStatus
from slivka.scheduler import Runner


class RunnerStub(Runner):
    temp_dir = tempfile.TemporaryDirectory()
    JOBS_DIR = temp_dir.name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.submit_stack = []

    def submit(self, cmd, cwd):
        self.submit_stack.append((cmd, cwd))
        return ''

    @classmethod
    def check_status(cls, job_id, cwd) -> JobStatus:
        return JobStatus.UNDEFINED


def runner_factory(base_command=[], inputs={}, arguments={}, outputs={}, env={}, cls=RunnerStub) -> Runner:
    return cls({
        'baseCommand': base_command,
        'inputs': inputs,
        'arguments': arguments,
        'outputs': outputs,
        'env': env
    })
