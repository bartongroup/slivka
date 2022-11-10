import os.path
import tempfile
from functools import partial
from unittest import mock

import mongomock
from nose.tools import assert_equal

import slivka.db
from slivka.db.helpers import insert_one, pull_one
from slivka.db.documents import JobRequest
from slivka.db.helpers import insert_many, pull_many
from slivka.scheduler import Scheduler
from slivka.utils import JobStatus
from . import BaseSelectorStub, MockRunner


class TestJobSubmission:
    _tempdir: tempfile.TemporaryDirectory

    @classmethod
    def setup_class(cls):
        slivka.db.mongo = mongomock.MongoClient()
        slivka.db.database = slivka.db.mongo.slivkadb
        cls._tempdir = tempfile.TemporaryDirectory()

    @classmethod
    def teardown_class(cls):
        del slivka.db.mongo
        del slivka.db.database
        cls._tempdir.cleanup()

    def setup(self):
        self.scheduler = Scheduler(self._tempdir.name)
        self.runner = MockRunner('stub', 'runner1')
        self.scheduler.add_runner(self.runner)
        self.scheduler.selectors['stub'] = BaseSelectorStub()
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


class TestAssignRunners:
    _tempdir: tempfile.TemporaryDirectory

    @classmethod
    def setup_class(cls):
        slivka.db.mongo = mongomock.MongoClient()
        slivka.db.database = slivka.db.mongo.slivkadb
        cls._tempdir = tempfile.TemporaryDirectory()

    @classmethod
    def teardown_class(cls):
        del slivka.db.mongo
        del slivka.db.database
        cls._tempdir.cleanup()

    def setup(self):
        self.scheduler = Scheduler(self._tempdir.name)
        self.runner = MockRunner('stub', 'runner1')
        self.scheduler.add_runner(self.runner)
        self.scheduler.selectors['stub'] = BaseSelectorStub()

    def test_runner_assigned(self):
        request = JobRequest(service='stub', inputs={'runner': 1})
        insert_one(slivka.db.database, request)
        self.scheduler._assign_runners(slivka.db.database)
        pull_one(slivka.db.database, request)
        assert_equal(request.runner, self.runner.name)

    def test_accepted_set(self):
        request = JobRequest(service='stub', inputs={'runner': 1})
        insert_one(slivka.db.database, request)
        self.scheduler._assign_runners(slivka.db.database)
        pull_one(slivka.db.database, request)
        assert_equal(request.status, JobStatus.ACCEPTED)

    def test_rejected_set(self):
        request = JobRequest(service='stub', inputs={})
        insert_one(slivka.db.database, request)
        self.scheduler._assign_runners(slivka.db.database)
        pull_one(slivka.db.database, request)
        assert_equal(request.status, JobStatus.REJECTED)


class TestStartJobs:
    _tempdir: tempfile.TemporaryDirectory

    @classmethod
    def setup_class(cls):
        slivka.db.mongo = mongomock.MongoClient()
        slivka.db.database = slivka.db.mongo.slivkadb
        cls._tempdir = tempfile.TemporaryDirectory()

    @classmethod
    def teardown_class(cls):
        del slivka.db.mongo
        del slivka.db.database
        cls._tempdir.cleanup()

    def setup(self):
        self.scheduler = Scheduler(self._tempdir.name)
        self.runner = MockRunner('stub', 'runner1')
        self.scheduler.add_runner(self.runner)

    def test_queued_status(self):
        request = JobRequest(service='stub', inputs={}, runner='runner1',
                             status=JobStatus.ACCEPTED)
        insert_one(slivka.db.database, request)
        self.scheduler._run_accepted(slivka.db.database)
        pull_one(slivka.db.database, request)
        assert_equal(request.status, JobStatus.QUEUED)

    def test_batch_start_called(self):
        input_sentinel = {'input': 'value'}
        request = JobRequest(service='stub', inputs=input_sentinel,
                             runner='runner1', status=JobStatus.ACCEPTED)
        insert_one(slivka.db.database, request)
        job_dir = os.path.join(self._tempdir.name, request.b64id)
        with mock.patch.object(
                self.runner, "batch_start",
                side_effect=partial(MockRunner.batch_start, self.runner)):
            self.scheduler._run_accepted(slivka.db.database)
            self.runner.batch_start.assert_called_once_with(
                [input_sentinel], [job_dir]
            )

    def test_missing_runner(self):
        request = JobRequest(service='stub', inputs={}, runner='runner0',
                             status=JobStatus.ACCEPTED)
        insert_one(slivka.db.database, request)
        self.scheduler._run_accepted(slivka.db.database)
        pull_one(slivka.db.database, request)
        assert_equal(request.status, JobStatus.ERROR)

    def test_batch_start_failure_job_deferred(self):
        request = JobRequest(service='stub', inputs={}, runner='runner1',
                             status=JobStatus.ACCEPTED)
        insert_one(slivka.db.database, request)
        with mock.patch.object(self.runner, "submit", side_effect=OSError):
            self.scheduler._run_accepted(slivka.db.database)
        pull_one(slivka.db.database, request)
        assert_equal(request.status, JobStatus.ACCEPTED)

    def test_batch_start_failure_job_failed(self):
        request = JobRequest(service='stub', inputs={}, runner='runner1',
                             status=JobStatus.ACCEPTED)
        insert_one(slivka.db.database, request)
        self.scheduler.set_failure_limit(0)
        with mock.patch.object(self.runner, "submit", side_effect=OSError):
            self.scheduler._run_accepted(slivka.db.database)
        pull_one(slivka.db.database, request)
        assert_equal(request.status, JobStatus.ERROR)
