import tempfile

import time
from .runners.runner import Runner, RunInfo


def _wait_for_completion(runner: Runner, job: RunInfo, timeout=None):
    if timeout is None:
        timeout = 8640000
    end_time = time.monotonic() + timeout
    while time.monotonic() <= end_time:
        state = runner.check_status(job.id, job.cwd)
        if state.is_finished():
            return state
        time.sleep(1)
    else:
        raise TimeoutError


def test_service(runner: Runner, inputs: dict, timeout=60, dir=None):
    with tempfile.TemporaryDirectory(dir=dir) as work_dir:
        job = runner.run(inputs, work_dir)
        state = _wait_for_completion(runner, job, timeout)
    return state


class TestJob:
    def __init__(self, inputs: dict, timeout: int = None):
        self._inputs = inputs
        self._timeout = timeout

    def __call__(self, runner, dir=None):
        return test_service(runner, self._inputs, self._timeout, dir)
