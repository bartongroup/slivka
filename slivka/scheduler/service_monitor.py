import threading
import time
from tempfile import TemporaryDirectory

from slivka import JobStatus
from slivka.scheduler.runners import Runner


class ServiceTestInterruptedError(Exception):
    pass


class ServiceTestFailedError(Exception):
    pass


class ServiceTestTimedOutError(Exception):
    pass


class ServiceTest:
    """ A service test encapsulating runner under test and input data.

    The test is intended to be run in an executor (e.g.
    :class:`concurrent.futures.Executor`) or a dedicated thread.
    It creates a job and periodically checks its status
    as the scheduler do.
    """

    def __init__(self, runner: Runner, test_data: dict, timeout=900):
        self._runner = runner
        self._test_data = test_data
        self._timeout = timeout
        self._interrupt = threading.Event()

    def run(self):
        with TemporaryDirectory() as dir_name:
            try:
                job = self._runner.start(self._test_data, dir_name)
            except Exception as e:
                raise ServiceTestFailedError from e
            timeout = time.monotonic() + self._timeout
            while True:
                try:
                    status = self._runner.check_status(job)
                except Exception as e:
                    raise ServiceTestFailedError from e
                if status.is_finished():
                    if status == JobStatus.COMPLETED:
                        return
                    if status in (JobStatus.INTERRUPTED, JobStatus.DELETED):
                        raise ServiceTestInterruptedError
                    else:
                        raise ServiceTestFailedError
                if time.monotonic() > timeout:
                    raise ServiceTestTimedOutError
                if self._interrupt.wait(1):
                    raise ServiceTestInterruptedError

    def interrupt(self):
        """ Interrupt the running test.

        The test will be interrupted as soon as possible if
        not already stopped by making the :meth:`run` method throw a
        ServiceTestInterruptedError.
        """
        self._interrupt.set()
