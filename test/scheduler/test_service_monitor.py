import itertools
from unittest import mock

import pytest

from slivka.scheduler.runners.runner import Runner, JobStatus
from slivka.scheduler.service_monitor import ServiceTest, ServiceTestOutcome, \
    TEST_STATUS_FAILED, TEST_STATUS_OK, TEST_STATUS_TIMEOUT, TEST_STATUS_INTERRUPTED


@pytest.fixture
def mock_runner():
    return mock.MagicMock(spec=Runner)


def test_service_test_fail_on_start(mock_runner):
    exception = Exception("init error")
    mock_runner.start.side_effect = exception
    test = ServiceTest(runner=mock_runner, test_data={})
    assert test.run() == ServiceTestOutcome(
        TEST_STATUS_FAILED,
        message="init error",
        cause=exception
    )


def test_service_test_fail_on_status_check(mock_runner):
    exception = BrokenPipeError("broken pipe")
    mock_runner.check_status.side_effect = exception
    test = ServiceTest(runner=mock_runner, test_data={})
    assert test.run() == ServiceTestOutcome(
        TEST_STATUS_FAILED,
        message="broken pipe",
        cause=exception
    )


@pytest.mark.parametrize(
    'return_status_iterator',
    [
        itertools.repeat(JobStatus.COMPLETED),
        itertools.chain([JobStatus.RUNNING], itertools.repeat(JobStatus.COMPLETED)),
        itertools.chain([JobStatus.QUEUED, JobStatus.RUNNING],
                        itertools.repeat(JobStatus.COMPLETED)),
        itertools.chain([JobStatus.ACCEPTED, JobStatus.RUNNING],
                        itertools.repeat(JobStatus.COMPLETED))
    ]
)
def test_service_test_job_successful(mock_runner, return_status_iterator):
    mock_runner.check_status.side_effect = return_status_iterator
    test = ServiceTest(runner=mock_runner, test_data={})
    assert test.run() == ServiceTestOutcome(
        TEST_STATUS_OK,
        message="",
        cause=None
    )


@pytest.mark.parametrize(
    "return_status",
    [
        JobStatus.REJECTED,
        JobStatus.FAILED,
        JobStatus.ERROR,
    ]
)
def test_service_test_job_unsuccessful(mock_runner, return_status):
    mock_runner.check_status.return_value = return_status
    test = ServiceTest(runner=mock_runner, test_data={})
    assert test.run() == ServiceTestOutcome(
        TEST_STATUS_FAILED,
        message="completed unsuccessfully",
        cause=None
    )


def test_service_test_job_timeout(mock_runner):
    mock_runner.check_status.return_value = JobStatus.RUNNING
    test = ServiceTest(runner=mock_runner, test_data={}, timeout=0)
    assert test.run() == ServiceTestOutcome(
        TEST_STATUS_TIMEOUT,
        message="timeout",
        cause=None
    )


def test_service_test_job_removed_from_system(mock_runner):
    mock_runner.check_status.return_value = JobStatus.DELETED
    test = ServiceTest(runner=mock_runner, test_data={})
    assert test.run() == ServiceTestOutcome(
        TEST_STATUS_INTERRUPTED,
        message="removed from the scheduling system",
        cause=None
    )


def test_service_test_job_interrupted(mock_runner):
    mock_runner.check_status.return_value = JobStatus.INTERRUPTED
    test = ServiceTest(runner=mock_runner, test_data={})
    assert test.run() == ServiceTestOutcome(
        TEST_STATUS_INTERRUPTED,
        message="removed from the scheduling system",
        cause=None
    )
