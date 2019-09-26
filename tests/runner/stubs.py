import tempfile

from slivka.scheduler import Runner


class RunnerStub(Runner):
    JOBS_DIR = tempfile.TemporaryDirectory()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.submit_stack = []

    def submit(self, cmd, cwd):
        self.submit_stack.append((cmd, cwd))