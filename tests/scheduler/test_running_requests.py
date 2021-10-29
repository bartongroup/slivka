import os
import tempfile
from unittest import mock

import bson
import mongomock
from nose.tools import assert_equal, assert_raises, assert_list_equal, \
    assert_sequence_equal

import slivka.db
from slivka.db.documents import JobRequest
from slivka.scheduler.runner import Command, Job
from slivka.scheduler.scheduler import Scheduler, REJECTED, ERROR, \
    ExecutionDeferred, ExecutionFailed
from . import BaseSelectorStub, make_starter

_tempdir = ...  # type: tempfile.TemporaryDirectory


def mock_start_commands(commands):
    return [Job(f"job{i:02d}", command.cwd)
            for i, command in enumerate(commands)]


def setup_module():
    global _tempdir
    _tempdir = tempfile.TemporaryDirectory()
    slivka.db.mongo = mongomock.MongoClient()
    slivka.db.database = slivka.db.mongo.slivkadb


def teardown_module():
    _tempdir.cleanup()
    del slivka.db.database
    del slivka.db.mongo


def test_grouping():
    scheduler = Scheduler(_tempdir.name)
    runner1 = make_starter('stub', 'runner1')
    runner2 = make_starter('stub', 'runner2')
    scheduler.add_runner(runner1)
    scheduler.add_runner(runner2)
    scheduler.selectors['stub'] = BaseSelectorStub()

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
    scheduler = Scheduler(_tempdir.name)
    runner = make_starter('stub', 'runner')
    requests = [
        JobRequest(_id=bson.ObjectId(), service='stub', inputs=mock.sentinel.inputs),
        JobRequest(_id=bson.ObjectId(), service='stub', inputs=mock.sentinel.inputs)
    ]
    with mock.patch.object(runner, "start", return_value=range(len(requests))):
        started = scheduler._start_requests(runner, requests)
    assert_list_equal([request for request, job in started], requests)


def test_returned_jobs():
    scheduler = Scheduler(_tempdir.name)
    starter = make_starter('stub', 'runner')
    starter.runner = mock.MagicMock()
    starter.runner.start.side_effect = mock_start_commands
    requests = [
        JobRequest(_id=bson.ObjectId(), service='stub', inputs=mock.sentinel.inputs),
        JobRequest(_id=bson.ObjectId(), service='stub', inputs=mock.sentinel.inputs)
    ]
    started = scheduler._start_requests(starter, requests)
    expected = [
        Job(id="job00", cwd=os.path.join(_tempdir.name, requests[0].b64id)),
        Job(id="job01", cwd=os.path.join(_tempdir.name, requests[1].b64id))
    ]
    assert_sequence_equal([job for _, job in started], expected)


def test_start_called():
    scheduler = Scheduler(_tempdir.name)
    starter = make_starter('stub', 'runner')
    starter.runner = mock.MagicMock()
    starter.runner.start.side_effect = mock_start_commands
    requests = [
        JobRequest(_id=bson.ObjectId(), service='stub', inputs=mock.sentinel.inputs),
        JobRequest(_id=bson.ObjectId(), service='stub', inputs=mock.sentinel.inputs)
    ]
    commands = [
        Command(args=[], cwd=os.path.join(_tempdir.name, req.b64id), env=starter.env)
        for req in requests
    ]
    scheduler._start_requests(starter, requests)
    assert_equal(
        starter.runner.start.call_args,
        mock.call(commands)
    )


def test_deferred_running():
    scheduler = Scheduler(_tempdir.name)
    starter = make_starter('stub', 'runner')
    starter.runner = mock.MagicMock()
    starter.runner.start.side_effect = OSError
    requests = [
        JobRequest(_id=bson.ObjectId(), service='stub', inputs=mock.sentinel.inputs),
        JobRequest(_id=bson.ObjectId(), service='stub', inputs=mock.sentinel.inputs)
    ]
    with assert_raises(ExecutionDeferred):
        scheduler._start_requests(starter, requests)


def test_failed_running():
    scheduler = Scheduler(_tempdir.name)
    starter = make_starter('stub', 'runner')
    starter.runner = mock.MagicMock()
    starter.runner.start.side_effect = OSError
    requests = [
        JobRequest(_id=bson.ObjectId(), service='stub', inputs=mock.sentinel.inputs),
        JobRequest(_id=bson.ObjectId(), service='stub', inputs=mock.sentinel.inputs)
    ]
    scheduler.set_failure_limit(0)
    with assert_raises(ExecutionFailed):
        scheduler._start_requests(starter, requests)


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
