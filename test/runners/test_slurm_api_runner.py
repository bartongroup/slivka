import os
from unittest import mock

import pytest
import requests

from slivka import JobStatus
from slivka.scheduler.runners import Command, Job, RunnerID, SlurmApiRunner
from slivka.scheduler.runners.slurm_api import (
    SlurmApiConfigurationError,
    SlurmApiError,
)


class Response:
    def __init__(self, data=None, status_code=200, text=""):
        self.data = data or {}
        self.status_code = status_code
        self.text = text
        self.ok = 200 <= status_code < 400
        self.content = b"{}" if data is not None else b""

    def json(self):
        return self.data


@pytest.fixture()
def credentials():
    with mock.patch.dict(
        os.environ,
        {"SLURM_API_USER": "alice", "SLURM_API_TOKEN": "secret"},
    ):
        yield


@pytest.fixture()
def session():
    with mock.patch.object(requests, "Session") as session_cls:
        yield session_cls.return_value


@pytest.fixture()
def runner(credentials, session):
    return SlurmApiRunner(
        RunnerID("example", "slurm-api"),
        command="example",
        args=[],
        consts={},
        outputs=[],
        env={"EXAMPLE": "1"},
        base_url="https://slurm.example.org/",
        partition="webservices",
        qos="immediate",
        account="web",
        time_limit=60,
        cpus_per_task=2,
        nodes="node[1-2]",
        ntasks=4,
        memory_per_node=2048,
        job_name="slivka-test",
    )


def test_submit_sends_batch_script_and_job_description(runner, session):
    session.request.return_value = Response({"job_id": 12345})

    job = runner.submit(Command(["echo", "hello world"], "/cluster/jobs/1"))

    assert job == Job("12345", "/cluster/jobs/1")
    _, url = session.request.call_args.args
    assert url == "https://slurm.example.org/v0.0.45/job/submit"
    kwargs = session.request.call_args.kwargs
    assert kwargs["headers"] == {
        "X-SLURM-USER-NAME": "alice",
        "X-SLURM-USER-TOKEN": "secret",
    }
    payload = kwargs["json"]
    assert "echo 'hello world'" in payload["script"]
    assert payload["job"] == {
        "current_working_directory": "/cluster/jobs/1",
        "standard_output": "stdout",
        "standard_error": "stderr",
        "environment": runner.env,
        "partition": "webservices",
        "qos": "immediate",
        "account": "web",
        "time_limit": 60,
        "cpus_per_task": 2,
        "nodes": "node[1-2]",
        "ntasks": 4,
        "memory_per_node": 2048,
        "job_name": "slivka-test",
    }
    assert kwargs["timeout"] == 30
    assert kwargs["verify"] is True


@pytest.mark.parametrize(
    "state, expected",
    [
        ("PENDING", JobStatus.QUEUED),
        ("RUNNING", JobStatus.RUNNING),
        ("FAILED", JobStatus.FAILED),
        ("CANCELLED", JobStatus.INTERRUPTED),
        ("UNKNOWN_STATE", JobStatus.UNKNOWN),
    ],
)
def test_check_status_maps_slurm_state(runner, session, state, expected):
    session.request.return_value = Response(
        {"jobs": [{"job_id": "123", "job_state": state}]}
    )

    assert runner.check_status(Job("123", "/missing")) == expected


def test_check_status_reads_finished_file_for_completed_job(
    runner, session, job_directory
):
    os.makedirs(job_directory)
    with open(os.path.join(job_directory, "finished"), "w") as fp:
        fp.write("1")
    session.request.return_value = Response(
        {"jobs": [{"job_id": "123", "job_state": "COMPLETED"}]}
    )

    assert runner.check_status(Job("123", job_directory)) == JobStatus.FAILED


def test_check_status_treats_missing_completed_file_as_running(runner, session):
    session.request.return_value = Response(
        {"jobs": [{"job_id": "123", "job_state": "COMPLETED"}]}
    )

    assert runner.check_status(Job("123", "/missing")) == JobStatus.RUNNING


def test_check_status_falls_back_to_finished_file_if_job_is_not_found(
    runner, session, job_directory
):
    os.makedirs(job_directory)
    with open(os.path.join(job_directory, "finished"), "w") as fp:
        fp.write("0")
    session.request.return_value = Response(status_code=404, text="not found")

    assert runner.check_status(Job("123", job_directory)) == JobStatus.COMPLETED


def test_cancel_sends_delete(runner, session):
    session.request.return_value = Response({})

    runner.cancel(Job("123", "/cluster/jobs/1"))

    method, url = session.request.call_args.args
    assert method == "DELETE"
    assert url == "https://slurm.example.org/v0.0.45/job/123"


def test_missing_credentials_fail_before_request(session):
    with mock.patch.dict(
        os.environ,
        {"SLURM_API_USER": "", "SLURM_API_TOKEN": ""},
    ):
        runner = SlurmApiRunner(
            RunnerID("example", "slurm-api"),
            command="example",
            args=[],
            consts={},
            outputs=[],
            env={},
            base_url="https://slurm.example.org",
        )
        with pytest.raises(SlurmApiConfigurationError) as exc_info:
            runner.submit(Command(["echo", "hello"], "/cluster/jobs/1"))

    assert "SLURM_API_USER" in str(exc_info.value)
    assert "SLURM_API_TOKEN" in str(exc_info.value)
    session.request.assert_not_called()


def test_http_error_includes_status_and_body(runner, session):
    session.request.return_value = Response(status_code=500, text="boom")

    with pytest.raises(SlurmApiError) as exc_info:
        runner.cancel(Job("123", "/cluster/jobs/1"))

    assert "500" in str(exc_info.value)
    assert "boom" in str(exc_info.value)
