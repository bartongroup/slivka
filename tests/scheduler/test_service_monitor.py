from unittest import mock

import mongomock
from nose.tools import assert_equal

import slivka.db
from slivka.db.documents import ServiceState, JobRequest
from slivka.db.helpers import insert_one

from slivka.scheduler import Runner, Scheduler
from slivka.scheduler.runners.runner import RunnerID


def setup_module():
    global database
    slivka.db.mongo = mongomock.MongoClient()
    database = slivka.db.database = slivka.db.mongo.slivkadb

def teardown_module():
    del slivka.db.database
    del slivka.db.mongo


def MockRunner(service, name):
    runner = mock.MagicMock(spec=Runner)
    runner.id = RunnerID(service, name)
    runner.service_name, runner.name = runner.id
    return runner


class TestServiceStatusUpdates:
    def setup(self):
        self.scheduler = Scheduler()
        self.runner = MockRunner('stub', 'default')
        self.scheduler.add_runner(self.runner)
        self.scheduler.reset_service_states()
        insert_one(database, JobRequest(service='stub', inputs={}))

    def test_service_initial(self):
        service_state = ServiceState.find_one(
            database, service='stub', runner='default'
        )
        assert_equal(service_state.state, service_state.State.OK)

    def test_service_warning(self):
        self.runner.batch_run.side_effect = RuntimeError
        self.scheduler.run_cycle()
        service_state = ServiceState.find_one(
            database, service='stub', runner='default'
        )
        assert_equal(service_state.state, service_state.State.WARNING)

    def test_service_failure(self):
        self.runner.batch_run.side_effect = RuntimeError
        self.scheduler.set_failure_limit(0)
        self.scheduler.run_cycle()
        service_state = ServiceState.find_one(
            database, service='stub', runner='default'
        )
        assert_equal(service_state.state, service_state.State.FAILURE)

    def test_service_recovery(self):
        self.runner.batch_run.side_effect = [RuntimeError, ()]
        self.scheduler.run_cycle()
        # one cycle is wasted on passing through backoff counter
        self.scheduler.run_cycle()
        self.scheduler.run_cycle()
        service_state = ServiceState.find_one(
            database, service='stub', runner='default'
        )
        assert_equal(service_state.state, service_state.State.OK)
