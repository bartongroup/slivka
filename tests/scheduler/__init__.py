from scheduler.starter import CommandStarter, RunnerID
from slivka.scheduler import BaseSelector, Runner
from slivka.scheduler.runner import Command, Job


class BaseSelectorStub(BaseSelector):
    def limit_runner1(self, inputs): return inputs.get('runner') == 1
    def limit_runner2(self, inputs): return inputs.get('runner') == 2
    def limit_default(self, inputs): return inputs.get('use_default', False)
    def limit_foo(self, inputs): return inputs.get('use_foo', False)
    def limit_bar(self, inputs): return inputs.get('use_bar', False)


def make_starter(service=None, runner=None, base_command="", args=None,
                 outputs=None, env=None):
    service_id = None
    if service and runner:
        service_id = RunnerID(service, runner)
    return CommandStarter(
        service_id, base_command, args or [], outputs or [], env or {}
    )
