from slivka.scheduler import Limiter


class RunnerStub:
    def __init__(self, command_def, name, **kwargs):
        self.name = name
        self.kwargs = kwargs


class LimiterStub(Limiter):
    def limit_default(self, inputs):
        return inputs.get('use_default', False)

    def limit_foo(self, inputs):
        return inputs.get('use_foo', False)

    def limit_bar(self, inputs):
        return inputs.get('use_bar', False)
