import tempfile
from nose.tools import assert_equal
from unittest import mock

import slivka.conf.loaders
from slivka import JobStatus
from slivka.db.documents import ServiceState
from slivka.scheduler.runner import Job
from slivka.scheduler.starter import CommandStarter
from slivka.scheduler.scheduler import _ServiceTesterThread, _ServiceStateHelper

ServiceTest = slivka.conf.loaders.ServiceConfig.ServiceTest


class TestServiceTestThread:
    def setup(self):
        self.mock_states_manager = mock.create_autospec(_ServiceStateHelper)
        self.mock_runner = mock.create_autospec(CommandStarter)
        self.mock_runner.service_name = "service_stub"
        self.mock_runner.name = "runner_stub"
        self.test_directory = tempfile.TemporaryDirectory()
        self.test = ServiceTest(parameters={"foo": "bar"}, timeout=0)
        self.service_tester = _ServiceTesterThread(
            self.mock_states_manager, self.test_directory.name)

    def teardown(self):
        self.test_directory.cleanup()

    def test_successful(self):
        def mock_start(reqs): return [Job("0", cwd) for inp, cwd in reqs]
        self.mock_runner.start.side_effect = mock_start
        self.mock_runner.status.return_value = [JobStatus.COMPLETED]
        self.service_tester.run_test(self.mock_runner, self.test)
        assert_equal(
            self.mock_states_manager.mock_calls[0],
            mock.call.update_state(
                "service_stub", "runner_stub", "start", ServiceState.OK, "OK")
        )
        assert_equal(
            self.mock_states_manager.mock_calls[1],
            mock.call.update_state(
                "service_stub", "runner_stub", "state", ServiceState.OK, "OK")
        )

    def test_start_failure(self):
        self.mock_runner.start.side_effect = OSError()
        self.service_tester.run_test(self.mock_runner, self.test)
        assert_equal(
            self.mock_states_manager.mock_calls[0],
            mock.call.update_state(
                "service_stub", "runner_stub", "start", ServiceState.DOWN, "")
        )

    def test_status_update_failure(self):
        def mock_start(reqs): return [Job("0", cwd) for inp, cwd in reqs]
        self.mock_runner.start.side_effect = mock_start
        self.mock_runner.status.side_effect = OSError()
        self.service_tester.run_test(self.mock_runner, self.test)
        assert_equal(
            self.mock_states_manager.update_state.mock_calls[0],
            mock.call(
                "service_stub", "runner_stub", "start", ServiceState.OK, "OK")
        )
        assert_equal(
            self.mock_states_manager.update_state.mock_calls[1],
            mock.call(
                "service_stub", "runner_stub", "state", ServiceState.DOWN, "")
        )

    def test_job_failed(self):
        def mock_start(reqs): return [Job("0", cwd) for inp, cwd in reqs]
        self.mock_runner.start.side_effect = mock_start
        self.mock_runner.status.return_value = [JobStatus.FAILED]
        self.service_tester.run_test(self.mock_runner, self.test)
        assert_equal(
            self.mock_states_manager.mock_calls[1],
            mock.call.update_state(
                "service_stub", "runner_stub", "state", ServiceState.DOWN,
                "Test failed"
            )
        )

    def test_job_interrupted(self):
        def mock_start(reqs): return [Job("0", cwd) for inp, cwd in reqs]
        self.mock_runner.start.side_effect = mock_start
        self.mock_runner.status.return_value = [JobStatus.INTERRUPTED]
        self.service_tester.run_test(self.mock_runner, self.test)
        assert_equal(
            self.mock_states_manager.mock_calls[1],
            mock.call.update_state(
                "service_stub", "runner_stub", "state", ServiceState.WARNING,
                "Test deleted"
            )
        )

    def test_job_timed_out(self):
        def mock_start(reqs): return [Job("0", cwd) for inp, cwd in reqs]
        self.mock_runner.start.side_effect = mock_start
        self.mock_runner.status.return_value = [JobStatus.RUNNING]
        self.service_tester.run_test(self.mock_runner, self.test)
        assert_equal(
            self.mock_states_manager.mock_calls[1],
            mock.call.update_state(
                "service_stub", "runner_stub", "state", ServiceState.WARNING,
                "Test timed out"
            )
        )
