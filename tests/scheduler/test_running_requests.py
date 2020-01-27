from collections import defaultdict
from functools import partial

from slivka.utils import BackoffCounter

try:
    import mock
except ImportError:
    import unittest.mock as mock

import pytest

from slivka import JobStatus
from slivka.db.documents import JobRequest, JobMetadata
from slivka.scheduler import RunInfo, Runner, Scheduler
# noinspection PyUnresolvedReferences
from . import mock_mongo, insert_jobs


@pytest.fixture
def runner_mock():
    runner = mock.MagicMock(spec=Runner)
    runner.run.return_value = RunInfo(id=0, cwd='/tmp')

    def batch_run(inputs):
        yield from (RunInfo(id=0, cwd='/tmp') for _ in inputs)

    runner.batch_run.side_effect = batch_run
    return runner


@pytest.mark.usefixtures('mock_mongo')
def test_batch_run_called(insert_jobs, runner_mock):
    jobs = [JobRequest('dummy', {'param': 0}), JobRequest('dummy', {'param': 1})]
    insert_jobs(jobs)
    requests = {runner_mock: jobs}
    scheduler = Scheduler()
    scheduler.run_requests(requests)
    runner_mock.batch_run.assert_called_once_with([{'param': 0}, {'param': 1}])


def test_request_state_queued_set(mock_mongo, insert_jobs, runner_mock):
    jobs = [JobRequest('dummy', {'param': 0})]
    insert_jobs(jobs)
    scheduler = Scheduler()
    scheduler.run_requests({runner_mock: jobs.copy()})
    it = JobRequest.find_one(mock_mongo, _id=jobs[0]['_id'])
    assert it.status == JobStatus.QUEUED


def test_failed_request_state(mock_mongo, insert_jobs, runner_mock):
    jobs = [JobRequest('dummy', {'param': 0})]
    insert_jobs(jobs)
    scheduler = Scheduler()
    runner_mock.batch_run.side_effect = RuntimeError
    scheduler.run_requests({runner_mock: jobs.copy()})
    it = JobRequest.find_one(mock_mongo, _id=jobs[0]['_id'])
    assert it.status == JobStatus.PENDING


def test_giveup_request_state(mock_mongo, insert_jobs, runner_mock):
    jobs = [JobRequest('dummy', {'param': 0})]
    insert_jobs(jobs)
    scheduler = Scheduler()
    patch = mock.patch.object(
        scheduler, '_backoff_counters',
        defaultdict(partial(BackoffCounter, max_tries=0))
    )
    runner_mock.batch_run.side_effect = RuntimeError
    with patch:
        scheduler.run_requests({runner_mock: jobs.copy()})
    it = JobRequest.find_one(mock_mongo, _id=jobs[0]['_id'])
    assert it.status == JobStatus.ERROR


@pytest.mark.usefixtures('mock_mongo')
def test_remove_processed_requests(insert_jobs, runner_mock):
    jobs = [JobRequest('dummy', {'param': 0}), JobRequest('dummy', {'param': 1})]
    insert_jobs(jobs)
    scheduler = Scheduler()
    scheduler.run_requests({runner_mock: jobs})
    assert len(jobs) == 0


@pytest.mark.usefixtures('mock_mongo')
def test_keep_unprocessed_requests(insert_jobs, runner_mock):
    jobs = [JobRequest('dummy', {'param': 0}), JobRequest('dummy', {'param': 1})]
    insert_jobs(jobs)
    scheduler = Scheduler()
    runner_mock.batch_run.side_effect = RuntimeError
    scheduler.run_requests({runner_mock: jobs})
    assert len(jobs) == 2


@pytest.mark.usefixtures('mock_mongo')
def test_remove_erroneous_requests(insert_jobs, runner_mock):
    jobs = [JobRequest('dummy', {'param': 0}), JobRequest('dummy', {'param': 1})]
    insert_jobs(jobs)
    scheduler = Scheduler()
    patch = mock.patch.object(
        scheduler, '_backoff_counters',
        defaultdict(partial(BackoffCounter, max_tries=0))
    )
    runner_mock.batch_run.side_effect = RuntimeError
    with patch:
        scheduler.run_requests({runner_mock: jobs})
    assert len(jobs) == 0


def test_insert_jobs_tracking_data(mock_mongo, insert_jobs, runner_mock):
    request = JobRequest('dummy', {'param': 0})
    insert_jobs([request])
    scheduler = Scheduler()
    scheduler.run_requests(({runner_mock: [request]}))
    job = JobMetadata.find_one(mock_mongo, uuid=request['uuid'])
    assert job['service'] == 'dummy'
    assert job['work_dir'] == '/tmp'
    assert job['runner_class'] == '%s.%s' % (runner_mock.__class__.__module__, runner_mock.__class__.__name__)
    assert job['job_id'] == 0
    assert job['status'] == JobStatus.QUEUED
