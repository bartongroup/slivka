import filecmp
import os
import tempfile
from collections import OrderedDict
from itertools import zip_longest

import pytest
import unittest.mock as mock

from .stubs import runner_factory, RunnerStub


# single job run tests

def test_run_count():
    runner = runner_factory(base_command=['mycommand'])
    runner.submit = mock.Mock(return_value='0xc0ffee')
    runner.run({})
    assert runner.submit.call_count == 1


def test_run_base_command_with_no_parameters():
    runner = runner_factory(base_command=['mycommand'])
    submit_mock = mock.Mock(return_value='0xc0ffee')
    runner.submit = submit_mock
    runner.run({})
    args, kwargs = submit_mock.call_args
    cmd, _ = args
    assert cmd == ['mycommand']


def test_run_command_with_arguments():
    runner = runner_factory(base_command='mycommand', arguments=['foo', 'bar', 'baz'])
    runner.submit = mock.Mock(return_value='0xc0ffee')
    runner.run({})
    args, kwargs = runner.submit.call_args
    cmd, _ = args
    assert cmd == ['mycommand', 'foo', 'bar', 'baz']


def test_run_command_with_parameters():
    runner = runner_factory(
        base_command='mycommand',
        arguments=['foo', 'bar'],
        inputs=OrderedDict([
            ('param1', {'arg': '-p1 $(value)'}),
            ('param2', {'arg': '-p2 $(value)'})
        ])
    )
    runner.submit = mock.Mock(return_value='0xc0ffee')
    runner.run({'param1': 'xxx', 'param2': 'yyy'})
    args, kwargs = runner.submit.call_args
    cmd, _ = args
    assert cmd == ['mycommand', '-p1', 'xxx', '-p2', 'yyy', 'foo', 'bar']


def test_returned_job_id():
    runner = runner_factory()
    runner.submit = mock.Mock(return_value='0xc0ffee')
    job_id, job_cwd = runner.run({})
    assert job_id == '0xc0ffee'


def test_job_working_directory():
    runner = runner_factory()
    runner.submit = mock.Mock(return_value='0xc0ffee')
    job_id, job_cwd = runner.run({})
    assert os.path.dirname(job_cwd) == RunnerStub.JOBS_DIR
    assert os.path.isdir(job_cwd)


# file linking tests

def test_link_created():
    runner = runner_factory(inputs={
        'input': {'arg': '$(value)', 'type': 'file', 'symlink': 'input.txt'}
    })
    infile = tempfile.NamedTemporaryFile()
    infile.write(b'hello world\n')
    infile.flush()
    runner.submit = mock.Mock(return_value='')
    runner.run({'input': infile.name})
    (cmd, cwd), _ = runner.submit.call_args
    path = os.path.join(cwd, 'input.txt')
    assert filecmp.cmp(infile.name, path), \
        'Files %s and %s are not identical' % (infile.name, path)


# batch run tests

def test_batch_run_count():
    runner = runner_factory(base_command=['mycommand'])
    runner.submit = mock.Mock(return_value='0xc0ffee')
    runner.batch_run([{}, {}, {}])
    assert runner.submit.call_count == 3


def test_batch_run_with_parameters():
    runner = runner_factory(
        base_command=['mycommand'],
        inputs={
            'param': {'arg': '$(value)'}
        }
    )
    runner.submit = mock.Mock(return_value='')
    params = ['foo', 'bar', 'baz']
    runner.batch_run([{'param': arg} for arg in params])
    for param, (args, kwargs) in zip_longest(params, runner.submit.call_args_list):
        cmd, cwd = args
        assert cmd == ['mycommand', param]
