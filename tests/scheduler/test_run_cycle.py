import itertools
from typing import Iterator
from unittest import mock

import mongomock
from nose.tools import assert_equal

import slivka.db
from slivka.db.documents import JobRequest
from slivka.db.helpers import insert_many, pull_many
from slivka.scheduler import Scheduler, Runner
from slivka.scheduler.runners.runner import RunnerID, RunInfo
from slivka.utils import JobStatus
from . import LimiterStub


def setup_module():
    slivka.db.mongo = mongomock.MongoClient()
    slivka.db.database = slivka.db.mongo.slivkadb

def teardown_module():
    del slivka.db.mongo
    del slivka.db.database


class MockRunner(Runner):
    next_job_id = itertools.count(0).__next__

    def __init__(self, service, name):
        self.id = RunnerID(service_name=service, runner_name=name)

    def batch_start(self, inputs_list) -> Iterator[RunInfo]:
        return [RunInfo(self.submit(None, '/tmp'), '/tmp') for _ in inputs_list]

    def submit(self, cmd, cwd):
        return self.next_job_id()

    def check_status(self, job_id, cwd) -> JobStatus:
        return JobStatus.COMPLETED


class TestJobSubmission:
    def setup(self):
        self.scheduler = Scheduler()
        self.runner = MockRunner('stub', 'runner1')
        self.scheduler.add_runner(self.runner)
        self.scheduler.limiters['stub'] = LimiterStub()
        self.requests = [
            JobRequest(service='stub', inputs={'runner': 1}),
            JobRequest(service='stub', inputs={'runner': 1})
        ]
        insert_many(slivka.db.database, self.requests)

    def test_completed(self):
        requests = self.requests
        self.scheduler.run_cycle()
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.COMPLETED)
        assert_equal(requests[1].state, JobStatus.COMPLETED)

    def test_failed(self):
        def check_status(job_id, cwd): return JobStatus.FAILED
        with mock.patch.object(self.runner, 'check_status', check_status):
            self.scheduler.run_cycle()
        requests = self.requests
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.FAILED)
        assert_equal(requests[1].state, JobStatus.FAILED)

    def test_submission_delayed(self):
        def submit(cmd, cwd): raise RuntimeError("failed")
        with mock.patch.object(self.runner, 'submit', submit):
            self.scheduler.run_cycle()
        requests = self.requests
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.ACCEPTED)
        assert_equal(requests[1].state, JobStatus.ACCEPTED)

    def test_failed_submission(self):
        def submit(cmd, cwd): raise RuntimeError("failed")
        self.scheduler.set_failure_limit(0)
        with mock.patch.object(self.runner, 'submit', submit):
            self.scheduler.run_cycle()
        requests = self.requests
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.ERROR)
        assert_equal(requests[1].state, JobStatus.ERROR)
