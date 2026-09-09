import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Sequence
from urllib.parse import urlsplit, urlunsplit

import requests

from slivka import JobStatus
from slivka.compat import resources
from ._bash_lex import bash_quote
from .grid_engine import _StatusLetterDict
from .runner import Runner, Job, Command

log = logging.getLogger('slivka.scheduler')

_runner_bash_tpl = resources.read_text(__package__, 'runner.bash.tpl')

_status_states = _StatusLetterDict({
    'BOOT_FAIL': JobStatus.ERROR,
    'CANCELLED': JobStatus.INTERRUPTED,
    'COMPLETED': JobStatus.COMPLETED,
    'CONFIGURING': JobStatus.QUEUED,
    'COMPLETING': JobStatus.RUNNING,
    'DEADLINE': JobStatus.DELETED,
    'FAILED': JobStatus.FAILED,
    'NODE_FAIL': JobStatus.ERROR,
    'OUT_OF_MEMORY': JobStatus.ERROR,
    'PENDING': JobStatus.QUEUED,
    'PREEMPTED': JobStatus.DELETED,
    'RUNNING': JobStatus.RUNNING,
    'RESV_DEL_HOLD': JobStatus.QUEUED,
    'REQUEUE_FED': JobStatus.QUEUED,
    'REQUEUE_HOLD': JobStatus.QUEUED,
    'REQUEUED': JobStatus.QUEUED,
    'RESIZING': JobStatus.QUEUED,
    'SIGNALING': JobStatus.CANCELLING,
    'STOPPED': JobStatus.INTERRUPTED,
    'SUSPENDED': JobStatus.QUEUED,
    'TIMEOUT': JobStatus.INTERRUPTED,
})

_structured_fields = (
    'partition',
    'qos',
    'account',
    'time_limit',
    'cpus_per_task',
    'nodes',
    'tasks',
    'memory_per_node',
    'name',
)

_structured_aliases = {
    'ntasks': 'tasks',
    'job_name': 'name',
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
        url_prefix='',
        api_version='v0.0.45',
        username_env='SLURM_API_USER',
        token_env='SLURM_API_TOKEN',
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
            raise SlurmApiConfigurationError('Slurm API base_url is required')
        self.base_url = self._normalize_base_url(base_url)
        self.url_prefix = self._normalize_url_prefix(url_prefix)
        self.api_path = self._api_path()
        self.api_root = f'{self.base_url}/{self.api_path}'
        self.api_version = api_version.strip('/')
        self.username_env = username_env
        self.token_env = token_env
        self.timeout = timeout
        self.verify = verify
        self.session = requests.Session()

    def submit(self, command: Command) -> Job:
        cmd = str.join(' ', map(bash_quote, command.args))
        script = self._build_script(cmd)
        job_desc = {
            'current_working_directory': command.cwd,
            'standard_output': 'stdout',
            'standard_error': 'stderr',
            'environment': self._environment(),
            **self.job_options,
        }
        payload = {'script': script, 'job': job_desc}
        self._write_submit_artifacts(command.cwd, script, job_desc)
        try:
            data = self._request('POST', 'job/submit', json=payload)
        except SlurmApiError as e:
            self._write_submit_error(command.cwd, str(e))
            raise
        self._write_json(command.cwd, 'slurm-api-response.json', data)
        job_id = data.get('job_id')
        if job_id is None:
            error = 'Slurm API submit response did not include job_id'
            self._write_submit_error(command.cwd, error)
            raise SlurmApiError(error)
        return Job(str(job_id), command.cwd)

    def batch_submit(self, commands: Sequence[Command]) -> Sequence[Job]:
        return list(map(self.submit, commands))

    def check_status(self, job: Job) -> JobStatus:
        return self.batch_check_status([job])[0]

    def batch_check_status(self, jobs: Sequence[Job]) -> Sequence[JobStatus]:
        states = self._job_states()
        result = []
        for job in jobs:
            state = states.get(job.id)
            status = _status_states[state] if state else None
            if status is None or status == JobStatus.COMPLETED:
                status = self._status_from_finished_file(job, default=status)
            result.append(status)
        return result

    def cancel(self, job: Job):
        self._request('DELETE', f'job/{job.id}')

    def batch_cancel(self, jobs: Sequence[Job]):
        for job in jobs:
            self.cancel(job)

    def _job_states(self) -> Dict[str, Any]:
        data = self._request('GET', 'jobs')
        states = {}
        for job_data in data.get('jobs', []):
            job_id = job_data.get('job_id')
            if job_id is not None:
                states[str(job_id)] = self._extract_state(job_data)
        return states

    def _status_from_finished_file(
        self, job: Job, default: JobStatus = None
    ) -> JobStatus:
        fn = os.path.join(job.cwd, 'finished')
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
    def _extract_state(job_data: Dict[str, Any]):
        state = job_data.get('job_state') or job_data.get('state')
        if isinstance(state, dict):
            state = state.get('current')
        if isinstance(state, list):
            state = state[0] if state else None
        if state is None:
            return None
        return str(state)

    def _build_script(self, cmd):
        return _runner_bash_tpl.format(cmd=cmd)

    def _environment(self):
        return [
            f'{key}={value}'
            for key, value in self.env.items()
            if value is not None
        ]

    def _write_submit_artifacts(self, cwd, script, job_desc):
        self._write_text(cwd, 'slurm-api-script.sh', script)
        self._write_json(
            cwd,
            'slurm-api-request.json',
            self._submit_request_artifact(job_desc),
        )

    def _submit_request_artifact(self, job_desc):
        safe_job_desc = {
            key: value for key, value in job_desc.items()
            if key != 'environment'
        }
        return {
            'method': 'POST',
            'path': f'/{self.api_path}/{self.api_version}/job/submit',
            'script': 'slurm-api-script.sh',
            'job': safe_job_desc,
        }

    def _write_submit_error(self, cwd, error):
        self._write_text(
            cwd,
            'slurm-api-error.txt',
            self._sanitize_artifact_text(error),
        )

    def _sanitize_artifact_text(self, text):
        secrets = [
            self.username_env,
            self.token_env,
            os.getenv(self.username_env),
            os.getenv(self.token_env),
            *self.env.values(),
        ]
        sanitized = text
        for secret in secrets:
            if secret:
                sanitized = sanitized.replace(str(secret), '<redacted>')
        return sanitized

    @staticmethod
    def _write_text(cwd, filename, text):
        os.makedirs(cwd, exist_ok=True)
        with open(os.path.join(cwd, filename), 'w') as fp:
            fp.write(text)

    @staticmethod
    def _write_json(cwd, filename, data):
        os.makedirs(cwd, exist_ok=True)
        with open(os.path.join(cwd, filename), 'w') as fp:
            json.dump(data, fp, indent=2, sort_keys=True)
            fp.write('\n')

    def _request(self, method, path, **kwargs):
        response = self.session.request(
            method,
            self._url(path),
            headers=self._headers(),
            timeout=self.timeout,
            verify=self.verify,
            **kwargs,
        )
        if not response.ok:
            text = response.text[:500]
            raise SlurmApiError(
                f'Slurm API {method} {path} failed with '
                f'{response.status_code}: {text}'
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
                'Missing Slurm API credential environment variable(s): '
                + ', '.join(missing)
            )
        return {
            'X-SLURM-USER-NAME': username,
            'X-SLURM-USER-TOKEN': token,
        }

    @staticmethod
    def _normalize_base_url(base_url):
        parts = urlsplit(base_url)
        path = parts.path.rstrip('/')
        if not parts.scheme or not parts.netloc:
            raise SlurmApiConfigurationError(
                'Slurm API base_url must include scheme and host, '
                'such as http://host:6820'
            )
        if path or parts.query or parts.fragment:
            raise SlurmApiConfigurationError(
                'Slurm API base_url must be the slurmrestd origin only; '
                'move reverse-proxy paths to url_prefix'
            )
        return urlunsplit((parts.scheme, parts.netloc, '', '', ''))

    @staticmethod
    def _normalize_url_prefix(url_prefix):
        return (url_prefix or '').strip('/')

    def _api_path(self):
        return '/'.join(
            part for part in (self.url_prefix, 'slurm')
            if part
        )

    def _url(self, path):
        return f"{self.api_root}/{self.api_version}/{path.lstrip('/')}"
