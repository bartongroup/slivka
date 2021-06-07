import filecmp
import os
import tempfile
import unittest.mock as mock
from itertools import zip_longest

from nose.tools import assert_equal, assert_list_equal

import slivka.conf
from slivka import JobStatus
from slivka.scheduler.runners import Job
from .stub import RunnerStub

Argument = slivka.conf.ServiceConfig.Argument


# single job run tests

def test_run_count():
    runner = RunnerStub(command=['mycommand'])
    runner.submit = mock.Mock(return_value='0xc0ffee')
    with tempfile.TemporaryDirectory() as cwd:
        runner.start({}, cwd)
    assert_equal(runner.submit.call_count, 1)


def test_run_base_command_with_no_parameters():
    runner = RunnerStub(command=['mycommand'])
    with tempfile.TemporaryDirectory() as cwd:
        runner.submit = mock.Mock(return_value=Job('0xc0ffee', cwd))
        runner.start({}, cwd)
    args, kwargs = runner.submit.call_args
    cmd, = args
    assert_list_equal(cmd.args, ['mycommand'])


def test_run_command_with_parameters():
    runner = RunnerStub(
        command='mycommand',
        args=[
            Argument('param1', "-p1 $(value)"),
            Argument('param2', "-p2 $(value)"),
            Argument("const1", "$(value)", default="foo"),
            Argument('const2', "$(value)", default="bar")
        ]
    )
    with tempfile.TemporaryDirectory() as cwd:
        runner.submit = mock.Mock(return_value=Job('0xc0ffee', cwd))
        runner.start({'param1': 'xxx', 'param2': 'yyy'}, cwd)
    args, kwargs = runner.submit.call_args
    cmd, = args
    assert_list_equal(cmd.args, ['mycommand', '-p1', 'xxx', '-p2', 'yyy', 'foo', 'bar'])


def test_returned_job_id():
    runner = RunnerStub()
    with tempfile.TemporaryDirectory() as cwd:
        runner.submit = mock.Mock(return_value=Job('0xc0ffee', cwd))
        job_id, job_cwd = runner.start({}, cwd)
    assert_equal(job_id, '0xc0ffee')


def test_job_working_directory():
    runner = RunnerStub()
    with tempfile.TemporaryDirectory() as cwd:
        runner.submit = mock.Mock(return_value=Job('0xc0ffee', cwd))
        job_cwd = runner.start({}, cwd).cwd
        assert_equal(job_cwd, cwd)
        assert os.path.isdir(job_cwd)


# file linking tests

def test_link_created():
    runner = RunnerStub(
        args=[Argument('input', "$(value)", symlink="input.txt")]
    )
    infile = tempfile.NamedTemporaryFile()
    infile.write(b'hello world\n')
    infile.flush()
    with tempfile.TemporaryDirectory() as cwd:
        runner.submit = mock.Mock(return_value=Job('', cwd))
        runner.start({'input': infile.name}, cwd)
        path = os.path.join(cwd, 'input.txt')
        assert filecmp.cmp(infile.name, path), \
            'Files %s and %s are not identical' % (infile.name, path)


def test_batch_run_file_linking():
    runner = RunnerStub(
        args=[Argument('input', "$(value)", symlink="input.txt")]
    )
    infile = tempfile.NamedTemporaryFile()
    infile.write(b'hello world\n')
    infile.flush()
    with tempfile.TemporaryDirectory() as jobs_dir:
        cwds = [os.path.join(jobs_dir, str(i)) for i in range(5)]
        runner.submit = mock.Mock(side_effect=[Job('', cwd) for cwd in cwds])
        runner.batch_start([{'input': infile.name}] * 5, cwds)
        for cwd in cwds:
            path = os.path.join(cwd, 'input.txt')
            assert filecmp.cmp(infile.name, path), \
                'Files %s and %s are not identical' % (infile.name, path)


# batch run tests

def test_batch_run_count():
    runner = RunnerStub(command=['mycommand'])
    runner.submit = mock.Mock(return_value='0xc0ffee')
    with tempfile.TemporaryDirectory() as cwd:
        runner.batch_start([{}, {}, {}], [cwd, cwd, cwd])
    assert_equal(runner.submit.call_count, 3)


def test_batch_run_with_parameters():
    runner = RunnerStub(
        command=['mycommand'],
        args=[Argument('param', "$(value)")]
    )
    params = ['foo', 'bar', 'baz']
    with tempfile.TemporaryDirectory() as cwd:
        runner.submit = mock.Mock(return_value=Job('', cwd))
        runner.batch_start([{'param': arg} for arg in params], [cwd] * len(params))
    assert_equal(runner.submit.call_count, len(params))
    for param, call_args in zip_longest(params, runner.submit.call_args_list):
        args, kwargs = call_args
        assert_list_equal(args[0].args, ['mycommand', param])


# batch status check tests

def test_batch_check_status():
    runner = RunnerStub()
    runner.check_status = mock.Mock(
        side_effect=(JobStatus.COMPLETED, JobStatus.DELETED, JobStatus.QUEUED)
    )
    stats = runner.batch_check_status([mock.Mock()] * 3)
    assert_list_equal(stats, [JobStatus.COMPLETED, JobStatus.DELETED, JobStatus.QUEUED])
