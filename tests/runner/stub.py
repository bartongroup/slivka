from slivka import JobStatus
from slivka.scheduler.runners import Runner, Command, Job


class RunnerStub(Runner):
    def __init__(self, runner_id=None, command=None, args=None, outputs=None, env=None):
        if env is None: env = {}
        if outputs is None: outputs = []
        if args is None: args = []
        if command is None: command = []
        super().__init__(runner_id, command, args, outputs, env)
        self.job_id = 'stub'
        self.status = JobStatus.QUEUED

    def submit(self, command: Command) -> Job:
        return Job(id=self.job_id, cwd=command.cwd)

    def check_status(self, job: Job) -> JobStatus:
        return self.status

    def cancel(self, job: Job):
        pass
