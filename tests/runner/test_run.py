import contextlib
import filecmp
import os
import tempfile
import unittest.mock as mock
from collections import OrderedDict
from itertools import zip_longest

from nose.tools import assert_equal, assert_list_equal

from slivka import JobStatus
from .stubs import runner_factory, RunnerStub


# single job run tests

def test_run_count():
    runner = runner_factory(base_command=['mycommand'])
    runner.submit = mock.Mock(return_value='0xc0ffee')
    runner.run({})
    assert_equal(runner.submit.call_count, 1)


def test_run_base_command_with_no_parameters():
    runner = runner_factory(base_command=['mycommand'])
    submit_mock = mock.Mock(return_value='0xc0ffee')
    runner.submit = submit_mock
    runner.run({})
    args, kwargs = submit_mock.call_args
    cmd, _ = args
    assert_list_equal(cmd, ['mycommand'])


def test_run_command_with_arguments():
    runner = runner_factory(base_command='mycommand', arguments=['foo', 'bar', 'baz'])
    runner.submit = mock.Mock(return_value='0xc0ffee')
    runner.run({})
    args, kwargs = runner.submit.call_args
    cmd, _ = args
    assert_list_equal(cmd, ['mycommand', 'foo', 'bar', 'baz'])


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
    assert_list_equal(cmd, ['mycommand', '-p1', 'xxx', '-p2', 'yyy', 'foo', 'bar'])


def test_returned_job_id():
    runner = runner_factory()
    runner.submit = mock.Mock(return_value='0xc0ffee')
    job_id, job_cwd = runner.run({})
    assert_equal(job_id, '0xc0ffee')


def test_job_working_directory():
    runner = runner_factory()
    runner.submit = mock.Mock(return_value='0xc0ffee')
    job_id, job_cwd = runner.run({})
    assert_equal(os.path.dirname(job_cwd), RunnerStub.JOBS_DIR)
    assert os.path.isdir(job_cwd)


def test_working_directory_cleanup():
    runner = runner_factory()
    MyError = type('MyError', (Exception,), {})
    runner.submit = mock.Mock(side_effect=MyError)
    with contextlib.suppress(MyError):
        runner.run({})
    (cmd, cwd), kwargs = runner.submit.call_args
    assert not os.path.exists(cwd)


def test_batch_working_directory_cleanup():
    runner = runner_factory()
    MyError = type('MyError', (Exception,), {})
    runner.submit = mock.Mock(side_effect=MyError)
    with contextlib.suppress(MyError):
        runner.batch_run([{}, {}, {}, {}])
    for args, kwargs in runner.submit.call_args_list:
        cmd, cwd = args
        assert not os.path.exists(cwd)


# file linking tests

def test_link_created():
    runner = runner_factory(inputs={
        'input': {'arg': '$(value)', 'type': 'file', 'symlink': 'input.txt'}
    })
    infile = tempfile.NamedTemporaryFile()
    infile.write(b'hello world\n')
    infile.flush()
    runner.submit = mock.Mock(return_value='')
    job_id, job_cwd = runner.run({'input': infile.name})
    path = os.path.join(job_cwd, 'input.txt')
    assert filecmp.cmp(infile.name, path), \
        'Files %s and %s are not identical' % (infile.name, path)


def test_batch_run_file_linking():
    runner = runner_factory(inputs={
        'input': {'arg': '$(value)', 'type': 'file', 'symlink': 'input.txt'}
    })
    infile = tempfile.NamedTemporaryFile()
    infile.write(b'hello world\n')
    infile.flush()
    runner.submit = mock.Mock(return_value='')
    results = runner.batch_run([{'input': infile.name}] * 5)
    for job_id, job_cwd in results:
        path = os.path.join(job_cwd, 'input.txt')
        assert filecmp.cmp(infile.name, path), \
            'Files %s and %s are not identical' % (infile.name, path)


# batch run tests

def test_batch_run_count():
    runner = runner_factory(base_command=['mycommand'])
    runner.submit = mock.Mock(return_value='0xc0ffee')
    runner.batch_run([{}, {}, {}])
    assert_equal(runner.submit.call_count, 3)


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
        assert_list_equal(cmd, ['mycommand', param])


# batch status check tests

def test_batch_check_status():
    LocalRunnerStub = type('Runner', (RunnerStub,), {})
    runner = runner_factory(cls=LocalRunnerStub)
    LocalRunnerStub.check_status = mock.Mock(
        side_effect=(JobStatus.COMPLETED, JobStatus.DELETED, JobStatus.QUEUED)
    )
    stats = runner.batch_check_status([mock.Mock()] * 3)
    assert_list_equal(stats, [JobStatus.COMPLETED, JobStatus.DELETED, JobStatus.QUEUED])
