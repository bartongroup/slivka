import itertools
from typing import List

from slivka import JobStatus
from slivka.scheduler import Limiter, Runner
from slivka.scheduler.runners.runner import RunnerID, Command, Job


class LimiterStub(Limiter):
    def limit_runner1(self, inputs): return inputs.get('runner') == 1
    def limit_runner2(self, inputs): return inputs.get('runner') == 2
    def limit_default(self, inputs): return inputs.get('use_default', False)
    def limit_foo(self, inputs): return inputs.get('use_foo', False)
    def limit_bar(self, inputs): return inputs.get('use_bar', False)


class MockRunner(Runner):

    def __init__(self, service, name):
        super().__init__(
            runner_id=RunnerID(service=service, runner=name),
            command=[], args=[], outputs=[], env={}
        )
        self.next_job_id = itertools.count(0).__next__

    def batch_start(self, inputs: List[dict], cwds: List[str]) -> List[Job]:
        return [self.submit(Command([], cwd)) for cwd in cwds]

    def submit(self, command: Command) -> Job:
        job_id = self.next_job_id()
        return Job(job_id, command.cwd)

    def check_status(self, job: Job) -> JobStatus:
        return JobStatus.QUEUED

    def cancel(self, job: Job):
        pass
