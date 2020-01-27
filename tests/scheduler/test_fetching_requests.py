from collections import defaultdict

import pytest

from slivka import JobStatus
from slivka.db.documents import JobRequest
from slivka.scheduler import Scheduler
from slivka.scheduler.core import RunnerSelector
# noinspection PyUnresolvedReferences
from . import mock_mongo, insert_jobs

runner_sentinel = object()


class RunnerSelectorStub(RunnerSelector):
    def select_runner(self, service, inputs):
        if inputs['param'] == 0:
            return self._null_runner
        else:
            return runner_sentinel


@pytest.mark.usefixtures('mock_mongo')
def test_fetched_requests(insert_jobs):
    jobs = [
        JobRequest('dummy', {'param': 0}),
        JobRequest('dummy', {'param': 1}),
        JobRequest('dummy', {'param': 1})
    ]
    insert_jobs(jobs)
    scheduler = Scheduler()
    scheduler.runner_selector = RunnerSelectorStub()
    accepted = defaultdict(list)
    scheduler.fetch_pending_requests(accepted)
    assert set(accepted[runner_sentinel]) == {jobs[1], jobs[2]}


def test_status_update(mock_mongo, insert_jobs):
    jobs = [
        JobRequest('dummy', {'param': 0}),
        JobRequest('dummy', {'param': 1})
    ]
    insert_jobs(jobs)
    db = mock_mongo
    scheduler = Scheduler()
    scheduler.runner_selector = RunnerSelectorStub()
    scheduler.fetch_pending_requests(defaultdict(list))

    assert JobRequest.find_one(db, _id=jobs[0]['_id']).status == JobStatus.REJECTED
    assert JobRequest.find_one(db, _id=jobs[1]['_id']).status == JobStatus.ACCEPTED
