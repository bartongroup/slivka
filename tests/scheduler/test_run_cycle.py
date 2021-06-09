import tempfile
from unittest import mock

import mongomock
from nose.tools import assert_equal

import slivka.db
from slivka.db.documents import JobRequest
from slivka.db.helpers import insert_many, pull_many
from slivka.scheduler import Scheduler
from slivka.utils import JobStatus
from . import LimiterStub, MockRunner


def setup_module():
    slivka.db.mongo = mongomock.MongoClient()
    slivka.db.database = slivka.db.mongo.slivkadb


def teardown_module():
    del slivka.db.mongo
    del slivka.db.database


class TestJobSubmission:
    @classmethod
    def setup_class(cls):
        cls._tempdir = tempfile.TemporaryDirectory()

    @classmethod
    def teardown_class(cls):
        cls._tempdir.cleanup()

    def setup(self):
        self.scheduler = Scheduler(self._tempdir.name)
        self.runner = MockRunner('stub', 'runner1')
        self.scheduler.add_runner(self.runner)
        self.scheduler.selectors['stub'] = LimiterStub()
        self.requests = [
            JobRequest(service='stub', inputs={'runner': 1}),
            JobRequest(service='stub', inputs={'runner': 1})
        ]
        insert_many(slivka.db.database, self.requests)

    def test_completed(self):
        with mock.patch.object(self.runner, "check_status",
                               return_value=JobStatus.COMPLETED):
            self.scheduler.main_loop()
        requests = self.requests
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.COMPLETED)
        assert_equal(requests[1].state, JobStatus.COMPLETED)

    def test_failed(self):
        with mock.patch.object(self.runner, 'check_status',
                               return_value=JobStatus.FAILED):
            self.scheduler.main_loop()
        requests = self.requests
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.FAILED)
        assert_equal(requests[1].state, JobStatus.FAILED)

    def test_submission_delayed(self):
        with mock.patch.object(self.runner, 'submit', side_effect=OSError):
            self.scheduler.main_loop()
        requests = self.requests
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.ACCEPTED)
        assert_equal(requests[1].state, JobStatus.ACCEPTED)

    def test_failed_submission(self):
        self.scheduler.set_failure_limit(0)
        with mock.patch.object(self.runner, 'submit', side_effect=OSError):
            self.scheduler.main_loop()
        requests = self.requests
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.ERROR)
        assert_equal(requests[1].state, JobStatus.ERROR)
