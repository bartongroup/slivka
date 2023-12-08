import threading
import time
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import timedelta
from tempfile import TemporaryDirectory
from typing import List

import pymongo.errors

from slivka import JobStatus
from slivka.consts import ServiceStatus
from slivka.db.repositories import ServiceStatusInfo
from slivka.scheduler.runners import Runner

ServiceTestOutcome = namedtuple("ServiceTestOutcome", "status, message, cause")

TEST_STATUS_OK = ServiceStatus.OK
TEST_STATUS_FAILED = ServiceStatus.DOWN
TEST_STATUS_INTERRUPTED = ServiceStatus.WARNING
TEST_STATUS_TIMEOUT = ServiceStatus.WARNING


class ServiceTest:
    """A service test encapsulating runner under test and input data.

    The test is intended to be run in an executor (e.g.
    :class:`concurrent.futures.Executor`) or a dedicated thread.
    It creates a job and periodically checks its status
    as the scheduler do.
    """

    def __init__(self, runner: Runner, test_parameters: dict, timeout=900):
        self._runner = runner
        self._test_parameters = test_parameters
        self._timeout = timeout
        self._interrupt = threading.Event()

    @property
    def runner(self):
        return self._runner

    def run(self, dir_name) -> ServiceTestOutcome:
        if self._interrupt.is_set():
            return ServiceTestOutcome(
                TEST_STATUS_INTERRUPTED, message="stopped", cause=None
            )
        try:
            job = self._runner.start(self._test_parameters, dir_name)
        except Exception as e:
            return ServiceTestOutcome(
                TEST_STATUS_FAILED, message=str(e), cause=e
            )
        timeout = time.monotonic() + self._timeout
        while True:
            try:
                status = self._runner.check_status(job)
            except Exception as e:
                return ServiceTestOutcome(
                    TEST_STATUS_FAILED, message=str(e), cause=e
                )
            if status.is_finished():
                if status == JobStatus.COMPLETED:
                    return ServiceTestOutcome(
                        TEST_STATUS_OK, message="", cause=None
                    )
                if status in (JobStatus.INTERRUPTED, JobStatus.DELETED):
                    return ServiceTestOutcome(
                        TEST_STATUS_INTERRUPTED,
                        message="removed from the scheduling system",
                        cause=None,
                    )
                else:
                    return ServiceTestOutcome(
                        TEST_STATUS_FAILED,
                        message="completed unsuccessfully",
                        cause=None,
                    )
            if time.monotonic() > timeout:
                return ServiceTestOutcome(
                    TEST_STATUS_TIMEOUT, message="timeout", cause=None
                )
            if self._interrupt.wait(2):
                return ServiceTestOutcome(
                    TEST_STATUS_INTERRUPTED,
                    message="interrupted",
                    cause=None,
                )

    def interrupt(self):
        """Interrupt the running test.

        The test will be interrupted as soon as possible if
        not already stopped. Currently running test will return
        _INTERRUPTED_ status.
        """
        self._interrupt.set()


class ServiceTestExecutorThread(threading.Thread):
    def __init__(self, repository, interval, temp_dir, name="ServiceTestThread"):
        threading.Thread.__init__(self, name=name)
        self._interval = (
            interval.total_seconds()
            if isinstance(interval, timedelta)
            else interval
        )
        self._repository = repository
        self._dir = temp_dir
        self._finished = threading.Event()
        self._tests: List[ServiceTest] = []

    def append_test(self, service_test):
        self._tests = [*self._tests, service_test]

    def extend_tests(self, iterable):
        self._tests = [*self._tests, *iterable]

    def run(self):
        while not self._finished.is_set():
            run_result = self.run_all_tests()
            with suppress(pymongo.errors.ConnectionFailure):
                for runner, test_outcome in run_result:
                    info = ServiceStatusInfo(
                        service=runner.service_name,
                        runner=runner.name,
                        status=test_outcome.status,
                        message=test_outcome.message
                    )
                    self._repository.insert(info)
            self._finished.wait(self._interval)

    def run_all_tests(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            tests = self._tests
            outcomes = executor.map(_run_with_tempdir(self._dir), tests)
            runners = (test.runner for test in tests)
            while True:
                try:
                    outcome = next(outcomes)
                except StopIteration:
                    break
                except Exception as e:
                    outcome = ServiceTestOutcome(
                        TEST_STATUS_FAILED,
                        message=f"uncaught error {e!r}",
                        cause=e,
                    )
                runner = next(runners)
                yield runner, outcome

    def shutdown(self):
        self._finished.set()
        for test in self._tests:
            test.interrupt()


def _run_with_tempdir(parent_dir):
    def wrapper(test: ServiceTest):
        with TemporaryDirectory(prefix='test-', dir=parent_dir) as temp_dir:
            return test.run(temp_dir)

    return wrapper
