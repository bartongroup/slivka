import tempfile
from unittest import mock

import mongomock
from nose.tools import assert_equal

import slivka.db
from slivka import JobStatus
from slivka.db.documents import JobRequest, CancelRequest, JobMetadata
from slivka.db.helpers import insert_one, pull_one
from slivka.scheduler import Scheduler
from . import BaseSelectorStub, MockRunner


def setup_module():
    slivka.db.mongo = mongomock.MongoClient()
    slivka.db.database = slivka.db.mongo.slivkadb


def teardown_module():
    del slivka.db.database
    del slivka.db.mongo


class TestJobCancelling:

    @classmethod
    def setup_class(cls):
        cls._tempdir = tempfile.TemporaryDirectory()

    @classmethod
    def teardown_class(cls):
        cls._tempdir.cleanup()

    def setup(self):
        self.scheduler = scheduler = Scheduler(self._tempdir.name)
        scheduler.add_runner(MockRunner('stub', 'runner1'))
        scheduler.selectors['stub'] = BaseSelectorStub()
        self.request = JobRequest(service='stub', inputs={'runner': 1})
        insert_one(slivka.db.database, self.request)

    def test_deleted(self):
        insert_one(slivka.db.database, CancelRequest(uuid=self.request.uuid))
        self.scheduler.main_loop()
        pull_one(slivka.db.database, self.request)
        assert_equal(self.request.state, JobStatus.DELETED)

    def test_cancelling(self):
        self.scheduler.main_loop()
        insert_one(slivka.db.database, CancelRequest(uuid=self.request.uuid))
        self.scheduler.main_loop()
        pull_one(slivka.db.database, self.request)
        assert_equal(self.request.state, JobStatus.CANCELLING)

    def test_cancel_called(self):
        runner = self.scheduler.runners['stub', 'runner1']
        self.scheduler.main_loop()
        insert_one(slivka.db.database, CancelRequest(uuid=self.request.uuid))
        job = JobMetadata.find_one(slivka.db.database, uuid=self.request.uuid)
        with mock.patch.object(runner, 'cancel') as mock_cancel:
            self.scheduler.main_loop()
            mock_cancel.assert_called_once_with((job.job_id, job.cwd))
