import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Sequence

import requests

from slivka import JobStatus
from slivka.compat import resources
from ._bash_lex import bash_quote
from .grid_engine import _StatusLetterDict
from .runner import Runner, Job, Command

log = logging.getLogger("slivka.scheduler")

_runner_bash_tpl = resources.read_text(__package__, "runner.bash.tpl")

_status_states = _StatusLetterDict({
    "BOOT_FAIL": JobStatus.ERROR,
    "CANCELLED": JobStatus.INTERRUPTED,
    "COMPLETED": JobStatus.COMPLETED,
    "CONFIGURING": JobStatus.QUEUED,
    "COMPLETING": JobStatus.RUNNING,
    "DEADLINE": JobStatus.DELETED,
    "FAILED": JobStatus.FAILED,
    "NODE_FAIL": JobStatus.ERROR,
    "OUT_OF_MEMORY": JobStatus.ERROR,
    "PENDING": JobStatus.QUEUED,
    "PREEMPTED": JobStatus.DELETED,
    "RUNNING": JobStatus.RUNNING,
    "RESV_DEL_HOLD": JobStatus.QUEUED,
    "REQUEUE_FED": JobStatus.QUEUED,
    "REQUEUE_HOLD": JobStatus.QUEUED,
    "REQUEUED": JobStatus.QUEUED,
    "RESIZING": JobStatus.QUEUED,
    "SIGNALING": JobStatus.CANCELLING,
    "STOPPED": JobStatus.INTERRUPTED,
    "SUSPENDED": JobStatus.QUEUED,
    "TIMEOUT": JobStatus.INTERRUPTED,
    # Keep compatibility with compact Slurm state codes used by squeue.
    "BF": JobStatus.ERROR,
    "CA": JobStatus.INTERRUPTED,
    "CD": JobStatus.COMPLETED,
    "CF": JobStatus.QUEUED,
    "CG": JobStatus.RUNNING,
    "DL": JobStatus.DELETED,
    "F": JobStatus.FAILED,
    "NF": JobStatus.ERROR,
    "OOM": JobStatus.ERROR,
    "PD": JobStatus.QUEUED,
    "PR": JobStatus.DELETED,
    "R": JobStatus.RUNNING,
    "RD": JobStatus.QUEUED,
    "RF": JobStatus.QUEUED,
    "RH": JobStatus.QUEUED,
    "RQ": JobStatus.QUEUED,
    "RS": JobStatus.QUEUED,
    "SI": JobStatus.CANCELLING,
    "ST": JobStatus.INTERRUPTED,
    "S": JobStatus.QUEUED,
    "TO": JobStatus.INTERRUPTED,
})

_structured_fields = (
    "partition",
    "qos",
    "account",
    "time_limit",
    "cpus_per_task",
    "nodes",
    "tasks",
    "memory_per_node",
    "name",
)

_structured_aliases = {
    "ntasks": "tasks",
    "job_name": "name",
}


class SlurmApiError(RuntimeError):
    pass


class SlurmApiConfigurationError(SlurmApiError):
    pass


class SlurmApiRunner(Runner):
    finished_job_timestamp = defaultdict(datetime.now)

    def __init__(
        self,
        *args,
        base_url=None,
        api_version="v0.0.45",
        username_env="SLURM_API_USER",
        token_env="SLURM_API_TOKEN",
        timeout=30,
        verify=True,
        **kwargs
    ):
        self.job_options = {
            field: kwargs.pop(field)
            for field in _structured_fields
            if field in kwargs and kwargs[field] is not None
        }
        self.job_options.update(
            (target, kwargs.pop(source))
            for source, target in _structured_aliases.items()
            if source in kwargs and kwargs[source] is not None
        )
        super().__init__(*args, **kwargs)
        if not base_url:
            raise SlurmApiConfigurationError("Slurm API base_url is required")
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version.strip("/")
        self.username_env = username_env
        self.token_env = token_env
        self.timeout = timeout
        self.verify = verify
        self.session = requests.Session()

    def submit(self, command: Command) -> Job:
        cmd = str.join(" ", map(bash_quote, command.args))
        script = self._build_script(cmd)
        job_desc = {
            "current_working_directory": command.cwd,
            "standard_output": "stdout",
            "standard_error": "stderr",
            "environment": self._environment(),
            **self.job_options,
        }
        data = self._request(
            "POST",
            "job/submit",
            json={"script": script, "job": job_desc},
        )
        job_id = data.get("job_id")
        if job_id is None:
            raise SlurmApiError("Slurm API submit response did not include job_id")
        return Job(str(job_id), command.cwd)

    def batch_submit(self, commands: Sequence[Command]) -> Sequence[Job]:
        return list(map(self.submit, commands))

    def check_status(self, job: Job) -> JobStatus:
        return self.batch_check_status([job])[0]

    def batch_check_status(self, jobs: Sequence[Job]) -> Sequence[JobStatus]:
        return [self._check_job_status(job) for job in jobs]

    def cancel(self, job: Job):
        self._request("DELETE", f"job/{job.id}")

    def batch_cancel(self, jobs: Sequence[Job]):
        for job in jobs:
            self.cancel(job)

    def _check_job_status(self, job: Job) -> JobStatus:
        data = self._request("GET", f"job/{job.id}", allow_not_found=True)
        job_data = self._find_job(data, job.id)
        state = self._extract_state(job_data)
        status = _status_states[state] if state else None
        if status is None or status == JobStatus.COMPLETED:
            return self._status_from_finished_file(job, default=status)
        return status

    def _status_from_finished_file(
        self, job: Job, default: JobStatus = None
    ) -> JobStatus:
        fn = os.path.join(job.cwd, "finished")
        try:
            with open(fn) as fp:
                return_code = int(fp.read())
            self.finished_job_timestamp.pop(job.id, None)
            return (
                JobStatus.COMPLETED if return_code == 0 else
                JobStatus.ERROR if return_code == 127 else
                JobStatus.INTERRUPTED if return_code >= 128 else
                JobStatus.INTERRUPTED if return_code < 0 else
                JobStatus.FAILED
            )
        except FileNotFoundError:
            if default is not None and default != JobStatus.COMPLETED:
                return default
            ts = self.finished_job_timestamp[job.id]
            if datetime.now() - ts < timedelta(minutes=1):
                return JobStatus.RUNNING
            del self.finished_job_timestamp[job.id]
            return JobStatus.INTERRUPTED

    @staticmethod
    def _find_job(data: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        if "jobs" in data:
            for job in data["jobs"]:
                if str(job.get("job_id")) == str(job_id):
                    return job
            return {}
        if "job" in data:
            return data["job"]
        return data

    @staticmethod
    def _extract_state(job_data: Dict[str, Any]):
        state = job_data.get("job_state") or job_data.get("state")
        if isinstance(state, dict):
            state = state.get("current")
        if isinstance(state, list):
            state = state[0] if state else None
        if state is None:
            return None
        return str(state)

    def _build_script(self, cmd):
        exports = "\n".join(
            f"export {key}={bash_quote(value)}"
            for key, value in self.env.items()
            if value is not None
        )
        if exports:
            cmd = exports + "\n" + cmd
        return _runner_bash_tpl.format(cmd=cmd)

    def _environment(self):
        return [
            f"{key}={value}"
            for key, value in self.env.items()
            if value is not None
        ]

    def _request(self, method, path, allow_not_found=False, **kwargs):
        response = self.session.request(
            method,
            self._url(path),
            headers=self._headers(),
            timeout=self.timeout,
            verify=self.verify,
            **kwargs,
        )
        if allow_not_found and response.status_code == 404:
            return {}
        if not response.ok:
            text = response.text[:500]
            raise SlurmApiError(
                f"Slurm API {method} {path} failed with "
                f"{response.status_code}: {text}"
            )
        if not response.content:
            return {}
        return response.json()

    def _headers(self):
        username = os.getenv(self.username_env)
        token = os.getenv(self.token_env)
        missing = [
            name for name, value in (
                (self.username_env, username),
                (self.token_env, token),
            )
            if not value
        ]
        if missing:
            raise SlurmApiConfigurationError(
                "Missing Slurm API credential environment variable(s): "
                + ", ".join(missing)
            )
        return {
            "X-SLURM-USER-NAME": username,
            "X-SLURM-USER-TOKEN": token,
        }

    def _url(self, path):
        return f"{self.base_url}/{self.api_version}/{path.lstrip('/')}"
