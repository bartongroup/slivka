from slivka.scheduler import Limiter


class LimiterStub(Limiter):
    def limit_runner1(self, inputs): return inputs.get('runner') == 1
    def limit_runner2(self, inputs): return inputs.get('runner') == 2
    def limit_default(self, inputs): return inputs.get('use_default', False)
    def limit_foo(self, inputs): return inputs.get('use_foo', False)
    def limit_bar(self, inputs): return inputs.get('use_bar', False)
