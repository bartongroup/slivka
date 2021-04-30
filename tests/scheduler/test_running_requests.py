from unittest import mock

import mongomock
from nose.tools import assert_list_equal, assert_sequence_equal

import slivka.db
from slivka.db.documents import JobRequest
from slivka.scheduler import Scheduler
from slivka.scheduler.core import REJECTED, ERROR
from slivka.scheduler.runners.runner import RunnerID, Runner
from slivka.utils import BackoffCounter
from . import LimiterStub


def MockRunner(service, name):
    runner = mock.MagicMock(spec=Runner)
    runner.id = RunnerID(service_name=service, runner_name=name)
    runner.service_name = service
    runner.name = name
    return runner


def setup_module():
    slivka.db.mongo = mongomock.MongoClient()
    slivka.db.database = slivka.db.mongo.slivkadb


def teardown_module():
    del slivka.db.database
    del slivka.db.mongo


def test_grouping():
    scheduler = Scheduler()
    runner1 = MockRunner('stub', 'runner1')
    runner2 = MockRunner('stub', 'runner2')
    scheduler.add_runner(runner1)
    scheduler.add_runner(runner2)
    scheduler.limiters['stub'] = LimiterStub()

    requests = [
        JobRequest(service='stub', inputs={'runner': 1}),
        JobRequest(service='stub', inputs={'runner': 2}),
        JobRequest(service='stub', inputs={'runner': 1}),
        JobRequest(service='stub', inputs={'runner': 0})
    ]
    grouped = scheduler.group_requests(requests)
    assert_list_equal(grouped[runner1], [requests[0], requests[2]])
    assert_list_equal(grouped[runner2], [requests[1]])
    assert_list_equal(grouped[REJECTED], [requests[3]])
    assert_list_equal(grouped[ERROR], [])


def test_successful_running():
    scheduler = Scheduler()
    runner = MockRunner('stub', 'runner')
    requests = [
        JobRequest(service='stub', inputs=mock.sentinel.inputs),
        JobRequest(service='stub', inputs=mock.sentinel.inputs)
    ]
    runner.batch_start.return_value = range(len(requests))
    started, deferred, failed = scheduler.run_requests(runner, requests)
    assert_list_equal([request for request, job in started], requests)


def test_returned_jobs():
    scheduler = Scheduler()
    runner = MockRunner('stub', 'runner')
    requests = [
        JobRequest(service='stub', inputs=mock.sentinel.inputs),
        JobRequest(service='stub', inputs=mock.sentinel.inputs)
    ]
    runner.batch_start.return_value = range(len(requests))
    started, deferred, failed = scheduler.run_requests(runner, requests)
    assert_list_equal([job for request, job in started], list(range(len(requests))))


def test_batch_run_called():
    scheduler = Scheduler()
    runner = MockRunner('stub', 'runner')
    requests = [
        JobRequest(service='stub', inputs=mock.sentinel.inputs),
        JobRequest(service='stub', inputs=mock.sentinel.inputs)
    ]
    runner.batch_start.return_value = range(len(requests))
    scheduler.run_requests(runner, requests)
    runner.batch_start.assert_called_once_with(
        [mock.sentinel.inputs, mock.sentinel.inputs]
    )


def test_deferred_running():
    scheduler = Scheduler()
    runner = MockRunner('stub', 'runner')
    requests = [
        JobRequest(service='stub', inputs=mock.sentinel.inputs),
        JobRequest(service='stub', inputs=mock.sentinel.inputs)
    ]
    runner.batch_start.side_effect = OSError("failed successfully")
    started, deferred, failed = scheduler.run_requests(runner, requests)
    assert_list_equal(deferred, requests)


def test_failed_running():
    scheduler = Scheduler()
    runner = MockRunner('stub', 'runner')
    requests = [
        JobRequest(service='stub', inputs=mock.sentinel.inputs),
        JobRequest(service='stub', inputs=mock.sentinel.inputs)
    ]
    runner.batch_start.side_effect = OSError("failed successfully")
    with mock.patch.dict(scheduler._backoff_counters,
                         {runner.start: BackoffCounter(0)}):
        started, deferred, failed = scheduler.run_requests(runner, requests)
    assert_sequence_equal(failed, requests)

# @pytest.fixture
# def runner_mock():
#     runner = mock.MagicMock(spec=Runner)
#     runner.run.return_value = RunInfo(id=0, cwd='/tmp')
#
#     def batch_run(inputs):
#         yield from (RunInfo(id=0, cwd='/tmp') for _ in inputs)
#
#     runner.batch_run.side_effect = batch_run
#     return runner
#
#
# @pytest.mark.usefixtures('mock_mongo')
# def test_batch_run_called(insert_jobs, runner_mock):
#     jobs = [JobRequest('dummy', {'param': 0}), JobRequest('dummy', {'param': 1})]
#     insert_jobs(jobs)
#     requests = {runner_mock: jobs}
#     scheduler = Scheduler()
#     scheduler.run_requests(requests)
#     runner_mock.batch_run.assert_called_once_with([{'param': 0}, {'param': 1}])
#
#
# def test_request_state_queued_set(mock_mongo, insert_jobs, runner_mock):
#     jobs = [JobRequest('dummy', {'param': 0})]
#     insert_jobs(jobs)
#     scheduler = Scheduler()
#     scheduler.run_requests({runner_mock: jobs.copy()})
#     it = JobRequest.find_one(mock_mongo, _id=jobs[0]['_id'])
#     assert it.status == JobStatus.QUEUED
#
#
# def test_failed_request_state(mock_mongo, insert_jobs, runner_mock):
#     jobs = [JobRequest('dummy', {'param': 0})]
#     insert_jobs(jobs)
#     scheduler = Scheduler()
#     runner_mock.batch_run.side_effect = RuntimeError
#     scheduler.run_requests({runner_mock: jobs.copy()})
#     it = JobRequest.find_one(mock_mongo, _id=jobs[0]['_id'])
#     assert it.status == JobStatus.PENDING
#
#
# def test_giveup_request_state(mock_mongo, insert_jobs, runner_mock):
#     jobs = [JobRequest('dummy', {'param': 0})]
#     insert_jobs(jobs)
#     scheduler = Scheduler()
#     patch = mock.patch.object(
#         scheduler, '_backoff_counters',
#         defaultdict(partial(BackoffCounter, max_tries=0))
#     )
#     runner_mock.batch_run.side_effect = RuntimeError
#     with patch:
#         scheduler.run_requests({runner_mock: jobs.copy()})
#     it = JobRequest.find_one(mock_mongo, _id=jobs[0]['_id'])
#     assert it.status == JobStatus.ERROR
#
#
# @pytest.mark.usefixtures('mock_mongo')
# def test_remove_processed_requests(insert_jobs, runner_mock):
#     jobs = [JobRequest('dummy', {'param': 0}), JobRequest('dummy', {'param': 1})]
#     insert_jobs(jobs)
#     scheduler = Scheduler()
#     scheduler.run_requests({runner_mock: jobs})
#     assert len(jobs) == 0
#
#
# @pytest.mark.usefixtures('mock_mongo')
# def test_keep_unprocessed_requests(insert_jobs, runner_mock):
#     jobs = [JobRequest('dummy', {'param': 0}), JobRequest('dummy', {'param': 1})]
#     insert_jobs(jobs)
#     scheduler = Scheduler()
#     runner_mock.batch_run.side_effect = RuntimeError
#     scheduler.run_requests({runner_mock: jobs})
#     assert len(jobs) == 2
#
#
# @pytest.mark.usefixtures('mock_mongo')
# def test_remove_erroneous_requests(insert_jobs, runner_mock):
#     jobs = [JobRequest('dummy', {'param': 0}), JobRequest('dummy', {'param': 1})]
#     insert_jobs(jobs)
#     scheduler = Scheduler()
#     patch = mock.patch.object(
#         scheduler, '_backoff_counters',
#         defaultdict(partial(BackoffCounter, max_tries=0))
#     )
#     runner_mock.batch_run.side_effect = RuntimeError
#     with patch:
#         scheduler.run_requests({runner_mock: jobs})
#     assert len(jobs) == 0
#
#
# def test_insert_jobs_tracking_data(mock_mongo, insert_jobs, runner_mock):
#     request = JobRequest('dummy', {'param': 0})
#     insert_jobs([request])
#     scheduler = Scheduler()
#     scheduler.run_requests(({runner_mock: [request]}))
#     job = JobMetadata.find_one(mock_mongo, uuid=request['uuid'])
#     assert job['service'] == 'dummy'
#     assert job['work_dir'] == '/tmp'
#     assert job['runner_class'] == '%s.%s' % (runner_mock.__class__.__module__, runner_mock.__class__.__name__)
#     assert job['job_id'] == 0
#     assert job['status'] == JobStatus.QUEUED
#
#
# @pytest.mark.usefixture('mock_mongo')
# def test_add_running_jobs(insert_jobs, runner_mock):
#     request = JobRequest('dummy', {'param': 0})
#     insert_jobs([request])
#     scheduler = Scheduler()
#     scheduler.run_requests({runner_mock: [request]})
#     running = scheduler.running_jobs[runner_mock.__class__]
#     assert len(running) == 1
#     assert running[0]['uuid'] == request['uuid']
