import os.path
import tempfile
from unittest import mock

import mongomock
from nose.tools import assert_equal

import slivka.db
from slivka.conf import ServiceConfig
from slivka.db.documents import JobRequest
from slivka.db.helpers import insert_many, pull_many
from slivka.db.helpers import insert_one, pull_one
from slivka.scheduler import Scheduler
from slivka.scheduler.runner import Job, Command
from slivka.utils import JobStatus
from . import BaseSelectorStub, make_starter

Argument = ServiceConfig.Argument


def setup_module():
    slivka.db.mongo = mongomock.MongoClient()
    slivka.db.database = slivka.db.mongo.slivkadb


def teardown_module():
    del slivka.db.mongo
    del slivka.db.database


def mock_start_commands(commands):
    return [Job(f"job{i:02d}", command.cwd)
            for i, command in enumerate(commands)]


def mock_status_factory(status):
    def status_fn(jobs):
        return [status for _ in jobs]
    return status_fn


class TestJobSubmission:
    _tempdir: tempfile.TemporaryDirectory

    @classmethod
    def setup_class(cls):
        cls._tempdir = tempfile.TemporaryDirectory()

    @classmethod
    def teardown_class(cls):
        cls._tempdir.cleanup()

    def setup(self):
        self.scheduler = Scheduler(self._tempdir.name)
        self.starter = make_starter('stub', 'runner1')
        self.starter.runner = mock.MagicMock()
        self.starter.runner.start.side_effect = mock_start_commands
        self.scheduler.add_runner(self.starter)
        self.scheduler.selectors['stub'] = BaseSelectorStub()
        self.requests = [
            JobRequest(service='stub', inputs={'runner': 1}),
            JobRequest(service='stub', inputs={'runner': 1})
        ]
        insert_many(slivka.db.database, self.requests)

    def test_completed(self):
        self.starter.runner.status.side_effect = mock_status_factory(JobStatus.COMPLETED)
        self.scheduler.main_loop()
        requests = self.requests
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.COMPLETED)
        assert_equal(requests[1].state, JobStatus.COMPLETED)

    def test_failed(self):
        self.starter.runner.status.side_effect = mock_status_factory(JobStatus.FAILED)
        self.scheduler.main_loop()
        requests = self.requests
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.FAILED)
        assert_equal(requests[1].state, JobStatus.FAILED)

    def test_submission_delayed(self):
        self.starter.runner.start.side_effect = OSError
        self.scheduler.main_loop()
        requests = self.requests
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.ACCEPTED)
        assert_equal(requests[1].state, JobStatus.ACCEPTED)

    def test_failed_submission(self):
        self.scheduler.set_failure_limit(0)
        self.starter.runner.start.side_effect = OSError
        self.scheduler.main_loop()
        requests = self.requests
        pull_many(slivka.db.database, requests)
        assert_equal(requests[0].state, JobStatus.ERROR)
        assert_equal(requests[1].state, JobStatus.ERROR)


class TestAssignRunners:
    _tempdir: tempfile.TemporaryDirectory

    @classmethod
    def setup_class(cls):
        cls._tempdir = tempfile.TemporaryDirectory()

    @classmethod
    def teardown_class(cls):
        cls._tempdir.cleanup()

    def setup(self):
        self.scheduler = Scheduler(self._tempdir.name)
        self.runner = make_starter('stub', 'runner1')
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
        cls._tempdir = tempfile.TemporaryDirectory()

    @classmethod
    def teardown_class(cls):
        cls._tempdir.cleanup()

    def setup(self):
        self.scheduler = Scheduler(self._tempdir.name)
        self.starter = make_starter(
            'stub', 'runner1', args=[Argument("input", "$(value)")])
        self.starter.runner = mock.MagicMock()
        self.starter.runner.start.side_effect = mock_start_commands
        self.scheduler.add_runner(self.starter)

    def test_queued_status(self):
        request = JobRequest(service='stub', inputs={}, runner='runner1',
                             status=JobStatus.ACCEPTED)
        insert_one(slivka.db.database, request)
        self.scheduler._run_accepted(slivka.db.database)
        pull_one(slivka.db.database, request)
        assert_equal(request.status, JobStatus.QUEUED)

    def test_start_called(self):
        input_sentinel = {'input': 'value'}
        request = JobRequest(service='stub', inputs=input_sentinel,
                             runner='runner1', status=JobStatus.ACCEPTED)
        insert_one(slivka.db.database, request)
        job_dir = os.path.join(self._tempdir.name, request.b64id)
        self.scheduler._run_accepted(slivka.db.database)
        assert_equal(
            self.starter.runner.start.call_args,
            mock.call([Command(["value"], job_dir, self.starter.env)])
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
        self.starter.runner.start.side_effect = OSError
        self.scheduler._run_accepted(slivka.db.database)
        pull_one(slivka.db.database, request)
        assert_equal(request.status, JobStatus.ACCEPTED)

    def test_batch_start_failure_job_failed(self):
        request = JobRequest(service='stub', inputs={}, runner='runner1',
                             status=JobStatus.ACCEPTED)
        insert_one(slivka.db.database, request)
        self.scheduler.set_failure_limit(0)
        self.starter.runner.start.side_effect = OSError
        self.scheduler._run_accepted(slivka.db.database)
        pull_one(slivka.db.database, request)
        assert_equal(request.status, JobStatus.ERROR)
