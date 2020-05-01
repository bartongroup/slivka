import itertools
from typing import Iterator
from unittest import mock

import pytest

from slivka import JobStatus
from slivka.db.documents import JobRequest, CancelRequest, JobMetadata
from slivka.db.helpers import insert_one, pull_one
from slivka.scheduler import Runner, Scheduler
from slivka.scheduler.runners.runner import RunnerID, RunInfo

from . import LimiterStub

# noinspection PyUnresolvedReferences
from . import mock_mongo


class MockRunner(Runner):
    next_job_id = itertools.count(0).__next__

    def __init__(self, service, name):
        self.id = RunnerID(service, name)

    def batch_run(self, inputs_list) -> Iterator[RunInfo]:
        return [RunInfo(self.submit(None, '/tmp'), '/tmp') for _ in inputs_list]

    def submit(self, cmd, cwd):
        job_id = self.next_job_id()
        return job_id

    def cancel(cls, job_id, cwd):
        pass


@pytest.fixture(scope='function')
def scheduler(mock_mongo):
    scheduler = Scheduler()
    runner = MockRunner('stub', 'runner1')
    scheduler.add_runner(runner)
    scheduler.limiters['stub'] = LimiterStub()
    return scheduler


def test_cancelled(mock_mongo, scheduler):
    request = JobRequest(service='stub', inputs={'runner': 1})
    insert_one(mock_mongo, request)
    insert_one(mock_mongo, CancelRequest(uuid=request.uuid))
    scheduler.run_cycle()
    pull_one(mock_mongo, request)
    assert request.state == JobStatus.DELETED


def test_cancelling_state_update(mock_mongo, scheduler):
    request = JobRequest(service='stub', inputs={'runner': 1})
    insert_one(mock_mongo, request)
    scheduler.run_cycle()
    insert_one(mock_mongo, CancelRequest(uuid=request.uuid))
    scheduler.run_cycle()
    pull_one(mock_mongo, request)
    assert request.state == JobStatus.CANCELLING


def test_cancel_called(mock_mongo, scheduler):
    runner = scheduler.runners['stub', 'runner1']
    request = JobRequest(service='stub', inputs={'runner': 1})
    insert_one(mock_mongo, request)
    scheduler.run_cycle()
    insert_one(mock_mongo, CancelRequest(uuid=request.uuid))
    job = JobMetadata.find_one(mock_mongo, uuid=request.uuid)
    with mock.patch.object(runner, 'cancel') as mock_cancel:
        scheduler.run_cycle()
        mock_cancel.assert_called_once_with(job.job_id, job.cwd)
