import itertools
from typing import Iterator
from unittest import mock

import mongomock
from nose.tools import assert_equal

import slivka.db
from slivka import JobStatus
from slivka.db.documents import JobRequest, CancelRequest, JobMetadata
from slivka.db.helpers import insert_one, pull_one
from slivka.scheduler import Runner, Scheduler
from slivka.scheduler.runners.runner import RunnerID, RunInfo
from . import LimiterStub


class MockRunner(Runner):
    next_job_id = itertools.count(0).__next__

    def __init__(self, service, name):
        self.id = RunnerID(service, name)

    def batch_start(self, inputs_list) -> Iterator[RunInfo]:
        return [RunInfo(self.submit(None, '/tmp'), '/tmp') for _ in inputs_list]

    def submit(self, cmd, cwd):
        job_id = self.next_job_id()
        return job_id

    def cancel(self, job_id, cwd):
        pass


def setup_module():
    slivka.db.mongo = mongomock.MongoClient()
    slivka.db.database = slivka.db.mongo.slivkadb

def teardown_module():
    del slivka.db.database
    del slivka.db.mongo


class TestJobCancelling:
    def setup(self):
        self.scheduler = scheduler = Scheduler()
        scheduler.add_runner(MockRunner('stub', 'runner1'))
        scheduler.limiters['stub'] = LimiterStub()
        scheduler.reset_service_states()
        self.request = JobRequest(service='stub', inputs={'runner': 1})
        insert_one(slivka.db.database, self.request)

    def test_deleted(self):
        insert_one(slivka.db.database, CancelRequest(uuid=self.request.uuid))
        self.scheduler.run_cycle()
        pull_one(slivka.db.database, self.request)
        assert_equal(self.request.state, JobStatus.DELETED)

    def test_cancelling(self):
        self.scheduler.run_cycle()
        insert_one(slivka.db.database, CancelRequest(uuid=self.request.uuid))
        self.scheduler.run_cycle()
        pull_one(slivka.db.database, self.request)
        assert_equal(self.request.state, JobStatus.CANCELLING)

    def test_cancel_called(self):
        runner = self.scheduler.runners['stub', 'runner1']
        self.scheduler.run_cycle()
        insert_one(slivka.db.database, CancelRequest(uuid=self.request.uuid))
        job = JobMetadata.find_one(slivka.db.database, uuid=self.request.uuid)
        with mock.patch.object(runner, 'cancel') as mock_cancel:
            self.scheduler.run_cycle()
            mock_cancel.assert_called_once_with(job.job_id, job.cwd)
