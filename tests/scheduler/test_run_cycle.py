from unittest import mock

import itertools
from typing import Iterator

from slivka.db.documents import JobRequest
from slivka.db.helpers import insert_many, pull_many
from slivka.scheduler import Scheduler, Runner
from slivka.scheduler.runners.runner import RunnerID, RunInfo
from slivka.utils import JobStatus
# noinspection PyUnresolvedReferences
from . import mock_mongo, insert_jobs, LimiterStub


class MockRunner(Runner):
    next_job_id = itertools.count(0).__next__

    def __init__(self, service, name):
        self.id = RunnerID(service_name=service, runner_name=name)

    def batch_run(self, inputs_list) -> Iterator[RunInfo]:
        return [RunInfo(self.submit(None, '/tmp'), '/tmp') for _ in inputs_list]

    def submit(self, cmd, cwd):
        return self.next_job_id()

    @classmethod
    def check_status(cls, job_id, cwd) -> JobStatus:
        return JobStatus.COMPLETED


def test_completed(mock_mongo):
    scheduler = Scheduler()
    runner = MockRunner('stub', 'runner1')
    scheduler.add_runner(runner)
    scheduler.limiters['stub'] = LimiterStub()

    requests = [
        JobRequest(service='stub', inputs={'runner': 1}),
        JobRequest(service='stub', inputs={'runner': 1})
    ]
    insert_many(mock_mongo, requests)
    scheduler.run_cycle()
    pull_many(mock_mongo, requests)
    assert requests[0].state == JobStatus.COMPLETED
    assert requests[1].state == JobStatus.COMPLETED


def test_failed(mock_mongo):
    scheduler = Scheduler()
    runner = MockRunner('stub', 'runner1')
    scheduler.add_runner(runner)
    scheduler.limiters['stub'] = LimiterStub()

    requests = [
        JobRequest(service='stub', inputs={'runner': 1}),
        JobRequest(service='stub', inputs={'runner': 1})
    ]
    insert_many(mock_mongo, requests)
    def check_status(job_id, cwd): return JobStatus.FAILED
    with mock.patch.object(MockRunner, 'check_status', check_status):
        scheduler.run_cycle()
    pull_many(mock_mongo, requests)
    assert requests[0].state == JobStatus.FAILED
    assert requests[1].state == JobStatus.FAILED


def test_delayed_submission(mock_mongo):
    scheduler = Scheduler()
    runner = MockRunner('stub', 'runner1')
    scheduler.add_runner(runner)
    scheduler.limiters['stub'] = LimiterStub()

    requests = [
        JobRequest(service='stub', inputs={'runner': 1}),
        JobRequest(service='stub', inputs={'runner': 1})
    ]
    insert_many(mock_mongo, requests)
    def submit(cmd, cwd): raise RuntimeError("failed")
    with mock.patch.object(runner, 'submit', submit):
        scheduler.run_cycle()
    pull_many(mock_mongo, requests)
    assert requests[0].state == JobStatus.ACCEPTED
    assert requests[1].state == JobStatus.ACCEPTED


def test_failed_submission(mock_mongo):
    scheduler = Scheduler()
    scheduler.set_failure_limit(0)
    runner = MockRunner('stub', 'runner1')
    scheduler.add_runner(runner)
    scheduler.limiters['stub'] = LimiterStub()

    requests = [
        JobRequest(service='stub', inputs={'runner': 1}),
        JobRequest(service='stub', inputs={'runner': 1})
    ]
    insert_many(mock_mongo, requests)
    def submit(cmd, cwd): raise RuntimeError("failed")
    with mock.patch.object(runner, 'submit', submit):
        scheduler.run_cycle()
    pull_many(mock_mongo, requests)
    assert requests[0].state == JobStatus.ERROR
    assert requests[1].state == JobStatus.ERROR
