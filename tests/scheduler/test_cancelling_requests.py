import tempfile
from unittest import mock

import mongomock
from nose.tools import assert_equal

import slivka.db
from slivka import JobStatus
from slivka.db.documents import JobRequest, CancelRequest
from slivka.db.helpers import insert_one, pull_one
from slivka.scheduler import Scheduler
from slivka.scheduler.runner import Job
from . import BaseSelectorStub, make_starter


def setup_module():
    slivka.db.mongo = mongomock.MongoClient()
    slivka.db.database = slivka.db.mongo.slivkadb


def teardown_module():
    del slivka.db.database
    del slivka.db.mongo


def mock_job_start(commands):
    return [Job(f"job{i:02d}", command.cwd)
            for i, command in enumerate(commands)]


class TestJobCancelling:
    _tempdir: tempfile.TemporaryDirectory

    @classmethod
    def setup_class(cls):
        cls._tempdir = tempfile.TemporaryDirectory()

    @classmethod
    def teardown_class(cls):
        cls._tempdir.cleanup()

    def setup(self):
        self.scheduler = scheduler = Scheduler(self._tempdir.name)
        self.starter = make_starter('stub', 'runner1')
        self.starter.runner = mock.MagicMock()
        self.starter.runner.start.side_effect = mock_job_start
        scheduler.add_runner(self.starter)
        scheduler.selectors['stub'] = BaseSelectorStub()
        self.request = JobRequest(service='stub', inputs={'runner': 1})
        insert_one(slivka.db.database, self.request)

    def test_deleted(self):
        insert_one(slivka.db.database, CancelRequest(job_id=self.request.id))
        self.scheduler.main_loop()
        pull_one(slivka.db.database, self.request)
        assert_equal(self.request.state, JobStatus.DELETED)

    def test_cancelling(self):
        self.scheduler.main_loop()
        insert_one(slivka.db.database, CancelRequest(job_id=self.request.id))
        self.scheduler.main_loop()
        pull_one(slivka.db.database, self.request)
        assert_equal(self.request.state, JobStatus.CANCELLING)

    def test_cancel_called(self):
        self.scheduler.main_loop()
        pull_one(slivka.db.database, self.request)
        job = self.request.job
        insert_one(slivka.db.database, CancelRequest(job_id=self.request.id))
        self.scheduler.main_loop()
        assert_equal(
            self.starter.runner.cancel.call_args,
            mock.call([Job(job['job_id'], job['work_dir'])])
        )
