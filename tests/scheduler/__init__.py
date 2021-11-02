from typing import List

from scheduler.starter import CommandStarter, RunnerID
from slivka import JobStatus
from slivka.scheduler import BaseSelector, Runner, BaseCommandRunner
from slivka.scheduler.runner import Command, Job


class BaseSelectorStub(BaseSelector):
    def limit_runner1(self, inputs): return inputs.get('runner') == 1
    def limit_runner2(self, inputs): return inputs.get('runner') == 2
    def limit_default(self, inputs): return inputs.get('use_default', False)
    def limit_foo(self, inputs): return inputs.get('use_foo', False)
    def limit_bar(self, inputs): return inputs.get('use_bar', False)


def make_starter(service=None, runner=None, base_command="", args=None,
                 env=None):
    service_id = None
    if service and runner:
        service_id = RunnerID(service, runner)
    return CommandStarter(
        service_id, base_command, args or [], env or {}
    )


class StubRunner(BaseCommandRunner):
    def __init__(self, **kwargs):
        self.init_kwargs = kwargs

    def start(self, commands: List[Command]) -> List[Job]:
        return [Job(f"job{i:02d}", command.cwd)
                for i, command in enumerate(commands)]

    def status(self, jobs: List[Job]) -> List[JobStatus]:
        return [JobStatus.RUNNING for _ in jobs]

    def cancel(self, jobs: List[Job]):
        pass
