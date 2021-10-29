import tempfile
from unittest import mock

import mongomock
from nose.tools import assert_equal

import slivka.db
from slivka import JobStatus
from slivka.db.documents import ServiceState, JobRequest
from slivka.db.helpers import insert_one
from slivka.scheduler import Scheduler
from slivka.scheduler.runner import Job
from . import make_starter

database = ...  # type: mongomock.Database
_tempdir = ...  # type: tempfile.TemporaryDirectory


def mock_start_commands(commands):
    return [Job(f"job{i:02d}", command.cwd)
            for i, command in enumerate(commands)]


def setup_module():
    global database, _tempdir
    _tempdir = tempfile.TemporaryDirectory()
    slivka.db.mongo = mongomock.MongoClient()
    database = slivka.db.database = slivka.db.mongo.slivkadb


def teardown_module():
    _tempdir.cleanup()
    del slivka.db.database
    del slivka.db.mongo


class TestServiceStatusUpdates:
    def setup(self):
        self.scheduler = Scheduler(_tempdir.name)
        self.starter = make_starter('stub', 'default')
        self.starter.runner = mock.MagicMock()
        self.starter.runner.start.side_effect = mock_start_commands
        self.scheduler.add_runner(self.starter)
        insert_one(database, JobRequest(service='stub', inputs={}))

    def test_service_successful(self):
        with mock.patch.object(self.starter, "status",
                               return_value=[JobStatus.QUEUED]):
            self.scheduler.main_loop()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.OK)

    def test_start_warning(self):
        with mock.patch.object(self.starter, "start", side_effect=OSError):
            self.scheduler.main_loop()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.WARNING)

    def test_start_failure(self):
        self.scheduler.set_failure_limit(0)
        with mock.patch.object(self.starter, "start", side_effect=OSError):
            self.scheduler.main_loop()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.DOWN)

    def test_start_recovery(self):
        with mock.patch.object(self.starter, "start",
                               side_effect=[OSError, ()]):
            self.scheduler.main_loop()
            # this cycle is wasted on passing through backoff counter
            self.scheduler.main_loop()
            self.scheduler.main_loop()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.OK)

    def test_service_error(self):
        with mock.patch.object(self.starter, "status",
                               return_value=[JobStatus.ERROR]):
            self.scheduler.main_loop()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.DOWN)

    def test_check_failed(self):
        with mock.patch.object(self.starter, "status",
                               side_effect=OSError):
            self.scheduler.main_loop()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.WARNING)

    @staticmethod
    def _get_state():
        return ServiceState.find_one(database, service='stub', runner='default')
