from unittest import mock

import mongomock
from nose.tools import assert_equal

import slivka.db
from slivka import JobStatus
from slivka.db.documents import ServiceState, JobRequest
from slivka.db.helpers import insert_one
from slivka.scheduler import Runner, Scheduler, RunInfo
from slivka.scheduler.runners.runner import RunnerID


def setup_module():
    global database
    slivka.db.mongo = mongomock.MongoClient()
    database = slivka.db.database = slivka.db.mongo.slivkadb


def teardown_module():
    del slivka.db.database
    del slivka.db.mongo


def create_mock_runner(service, name):
    runner = mock.MagicMock(spec=Runner)
    runner.id = RunnerID(service, name)
    runner.service_name, runner.name = runner.id
    return runner


class TestServiceStatusUpdates:
    def setup(self):
        self.scheduler = Scheduler()
        self.runner = create_mock_runner('stub', 'default')
        self.scheduler.add_runner(self.runner)
        insert_one(database, JobRequest(service='stub', inputs={}))

    def test_service_successful(self):
        self.runner.batch_start.return_value = [RunInfo('0', '/tmp')]
        self.runner.batch_check_status.return_value = [JobStatus.QUEUED]
        self.scheduler.run_cycle()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.OK)

    def test_start_warning(self):
        self.runner.batch_start.side_effect = OSError
        self.scheduler.run_cycle()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.WARNING)

    def test_start_failure(self):
        self.runner.batch_start.side_effect = OSError
        self.scheduler.set_failure_limit(0)
        self.scheduler.run_cycle()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.DOWN)

    def test_start_recovery(self):
        self.runner.batch_start.side_effect = [OSError, ()]
        self.scheduler.run_cycle()
        # one cycle is wasted on passing through backoff counter
        self.scheduler.run_cycle()
        self.scheduler.run_cycle()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.OK)

    def test_service_error(self):
        self.runner.batch_start.return_value = [RunInfo('0', '/tmp')]
        self.runner.batch_check_status.return_value = [JobStatus.ERROR]
        self.scheduler.run_cycle()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.DOWN)

    def test_check_failed(self):
        self.runner.batch_start.return_value = [RunInfo('0', '/tmp')]
        self.runner.batch_check_status.side_effect = OSError
        self.scheduler.run_cycle()
        service_state = self._get_state()
        assert_equal(service_state.state, ServiceState.WARNING)

    @staticmethod
    def _get_state():
        return ServiceState.find_one(database, service='stub', runner='default')
