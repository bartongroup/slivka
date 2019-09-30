import tempfile

from slivka.scheduler import Runner


class RunnerStub(Runner):
    temp_dir = tempfile.TemporaryDirectory()
    JOBS_DIR = temp_dir.name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


def runner_factory(base_command=[], inputs={}, arguments={}, outputs={}, env={}, cls=RunnerStub) -> Runner:
    return cls({
        'baseCommand': base_command,
        'inputs': inputs,
        'arguments': arguments,
        'outputs': outputs,
        'env': env
    })
