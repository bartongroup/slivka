import os
from unittest import mock

import pytest
import yaml

from slivka.scheduler.core import RunnerSelector, DefaultLimiter
from tests.runner_selector import RunnerStub


@pytest.fixture('module')
def no_limiter_conf():
    fp = os.path.join(os.path.dirname(__file__), 'no_limiter_conf.yaml')
    with open(fp) as f:
        return yaml.safe_load(f)


@pytest.fixture('module')
def limited_conf():
    fp = os.path.join(os.path.dirname(__file__), 'limiter_conf.yaml')
    with open(fp) as f:
        return yaml.safe_load(f)


@pytest.fixture('module', autouse=True)
def mock_runner():
    with mock.patch('slivka.scheduler.runners.Runner') as mock_runner:
        yield mock_runner


def test_runner_construction(no_limiter_conf):
    selector = RunnerSelector()
    selector.add_runners('test', no_limiter_conf)
    runner = selector.runners['test', 'default']
    assert isinstance(runner, RunnerStub)
    assert runner.kwargs == {"run_name": "foo"}


def test_internal_runner_construction(no_limiter_conf, mock_runner):
    selector = RunnerSelector()
    selector.add_runners('test', no_limiter_conf)
    runner = selector.runners['test', 'foo_conf']
    assert runner is mock_runner()


def test_default_limiter_present(no_limiter_conf):
    selector = RunnerSelector()
    selector.add_runners('test', no_limiter_conf)
    assert 'test' in selector.limiters
    assert isinstance(selector.limiters['test'], DefaultLimiter)


def test_default_runner_selection(no_limiter_conf):
    selector = RunnerSelector()
    selector.add_runners('test', no_limiter_conf)
    runner = selector.select_runner('test', {})
    assert isinstance(runner, RunnerStub)


def test_runner_selection(limited_conf):
    selector = RunnerSelector()
    selector.add_runners('test', limited_conf)
    runner = selector.select_runner('test', {'use_foo': True})
    assert runner.name == 'test-foo'


def test_no_runner_selected(limited_conf):
    selector = RunnerSelector()
    selector.add_runners('test', limited_conf)
    runner = selector.select_runner('test', {'use_nothing': True})
    assert runner is None
