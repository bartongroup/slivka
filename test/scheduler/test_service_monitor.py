import itertools
from unittest import mock

import pytest

from slivka.db.repositories import ServiceStatusRepository
from slivka.scheduler.runners.runner import JobStatus, Runner
from slivka.scheduler.service_monitor import (
    TEST_STATUS_FAILED,
    TEST_STATUS_INTERRUPTED,
    TEST_STATUS_OK,
    TEST_STATUS_TIMEOUT,
    ServiceTest,
    ServiceTestExecutorThread,
    ServiceTestOutcome,
)


@pytest.fixture
def mock_runner():
    return mock.MagicMock(spec=Runner)


@pytest.fixture
def mock_repository():
    return mock.MagicMock(spec=ServiceStatusRepository)


def test_service_test_fail_on_start(mock_runner, tmp_path):
    exception = Exception("init error")
    mock_runner.start.side_effect = exception
    test = ServiceTest(runner=mock_runner, test_parameters={})
    assert test.run(tmp_path) == ServiceTestOutcome(
        TEST_STATUS_FAILED, message="init error", cause=exception
    )


def test_service_test_fail_on_status_check(mock_runner, tmp_path):
    exception = BrokenPipeError("broken pipe")
    mock_runner.check_status.side_effect = exception
    test = ServiceTest(runner=mock_runner, test_parameters={})
    assert test.run(tmp_path) == ServiceTestOutcome(
        TEST_STATUS_FAILED, message="broken pipe", cause=exception
    )


@pytest.mark.parametrize(
    "return_status_iterator",
    [
        itertools.repeat(JobStatus.COMPLETED),
        itertools.chain(
            [JobStatus.RUNNING], itertools.repeat(JobStatus.COMPLETED)
        ),
        itertools.chain(
            [JobStatus.QUEUED, JobStatus.RUNNING],
            itertools.repeat(JobStatus.COMPLETED),
        ),
        itertools.chain(
            [JobStatus.ACCEPTED, JobStatus.RUNNING],
            itertools.repeat(JobStatus.COMPLETED),
        ),
    ],
)
def test_service_test_job_successful(
    mock_runner, return_status_iterator, tmp_path
):
    mock_runner.check_status.side_effect = return_status_iterator
    test = ServiceTest(runner=mock_runner, test_parameters={})
    assert test.run(tmp_path) == ServiceTestOutcome(
        TEST_STATUS_OK, message="", cause=None
    )


@pytest.mark.parametrize(
    "return_status",
    [
        JobStatus.REJECTED,
        JobStatus.FAILED,
        JobStatus.ERROR,
    ],
)
def test_service_test_job_unsuccessful(mock_runner, return_status, tmp_path):
    mock_runner.check_status.return_value = return_status
    test = ServiceTest(runner=mock_runner, test_parameters={})
    assert test.run(tmp_path) == ServiceTestOutcome(
        TEST_STATUS_FAILED, message="completed unsuccessfully", cause=None
    )


def test_service_test_job_timeout(mock_runner, tmp_path):
    mock_runner.check_status.return_value = JobStatus.RUNNING
    test = ServiceTest(runner=mock_runner, test_parameters={}, timeout=0)
    assert test.run(tmp_path) == ServiceTestOutcome(
        TEST_STATUS_TIMEOUT, message="timeout", cause=None
    )


def test_service_test_job_removed_from_system(mock_runner, tmp_path):
    mock_runner.check_status.return_value = JobStatus.DELETED
    test = ServiceTest(runner=mock_runner, test_parameters={})
    assert test.run(tmp_path) == ServiceTestOutcome(
        TEST_STATUS_INTERRUPTED,
        message="removed from the scheduling system",
        cause=None,
    )


def test_service_test_job_interrupted(mock_runner, tmp_path):
    mock_runner.check_status.return_value = JobStatus.INTERRUPTED
    test = ServiceTest(runner=mock_runner, test_parameters={})
    assert test.run(tmp_path) == ServiceTestOutcome(
        TEST_STATUS_INTERRUPTED,
        message="removed from the scheduling system",
        cause=None,
    )


def test_executor_run_tests_all_success(mock_runner, mock_repository, tmp_path):
    executor = ServiceTestExecutorThread(mock_repository, tmp_path)
    mock_runner.check_status.return_value = JobStatus.COMPLETED
    tests = [
        ServiceTest(runner=mock_runner, test_parameters={}),
        ServiceTest(runner=mock_runner, test_parameters={}),
        ServiceTest(runner=mock_runner, test_parameters={}),
    ]
    outcomes = executor.run_tests(tests)
    expected_outcomes = [
        ServiceTestOutcome(TEST_STATUS_OK, "", None),
        ServiceTestOutcome(TEST_STATUS_OK, "", None),
        ServiceTestOutcome(TEST_STATUS_OK, "", None),
    ]
    assert list(outcomes) == list(zip(tests, expected_outcomes))
