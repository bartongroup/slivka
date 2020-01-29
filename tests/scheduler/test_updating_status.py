from collections import defaultdict
from functools import partial
from typing import List, Callable, Iterator
from unittest import mock

import pytest

from slivka import JobStatus
from slivka.db.documents import JobRequest, JobMetadata
from slivka.scheduler import RunInfo, Runner, Scheduler
# noinspection PyUnresolvedReferences
from slivka.utils import BackoffCounter
from . import mock_mongo, insert_jobs


class RunnerStub(Runner):
    # noinspection PyMissingConstructor
    def __init__(self):
        pass

    def submit(self, cmd, cwd):
        raise NotImplementedError

    def batch_run(self, inputs_list) -> Iterator[RunInfo]:
        yield from (RunInfo(id=0, cwd='/tmp') for _ in inputs_list)

    @classmethod
    def check_status(cls, job_id, cwd) -> JobStatus:
        return JobStatus.RUNNING

    @classmethod
    def cancel(cls, job_id, cwd):
        raise NotImplementedError


def test_status_update(mock_mongo, insert_jobs):
    requests = insert_jobs([JobRequest('dummy', {'param': 0})])
    job_uuid = requests[0]['uuid']
    runner = RunnerStub()
    scheduler = Scheduler()
    scheduler.run_requests({runner: requests.copy()})
    with mock.patch.object(RunnerStub, 'check_status') as check_status_mock:
        check_status_mock.return_value = JobStatus.RUNNING
        scheduler.update_running_jobs()
    request = JobRequest.find_one(mock_mongo, uuid=job_uuid)
    job = JobMetadata.find_one(mock_mongo, uuid=job_uuid)
    assert request.status == JobStatus.RUNNING
    assert job.status == JobStatus.RUNNING


def test_failed_job_status(mock_mongo, insert_jobs):
    requests = insert_jobs([JobRequest('dummy', {'param': 0})])
    job_uuid = requests[0]['uuid']
    runner = RunnerStub()
    scheduler = Scheduler()
    scheduler.run_requests({runner: requests.copy()})
    counters_patch = mock.patch.object(
        scheduler, '_backoff_counters',
        defaultdict(partial(BackoffCounter, max_tries=0))
    )
    check_status_patch = mock.patch.object(RunnerStub, 'check_status')
    with check_status_patch as check_status_mock, counters_patch:
        check_status_mock.side_effect = RuntimeError
        scheduler.update_running_jobs()
    request = JobRequest.find_one(mock_mongo, uuid=job_uuid)
    job = JobMetadata.find_one(mock_mongo, uuid=job_uuid)
    assert request.status == JobStatus.ERROR
    assert job.status == JobStatus.ERROR
