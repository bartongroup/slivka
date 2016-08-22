import tempfile
import unittest

from pybioas.scheduler.command import CommandOption, FileResult
from pybioas.scheduler.executors import Executor, Job

try:
    import unittest.mock as mock
except ImportError:
    import mock

import pybioas.config

mock.patch.object = mock.patch.object

settings_mock = mock.create_autospec(pybioas.config.Settings)
tmp_dir = tempfile.TemporaryDirectory()
settings_mock.WORK_DIR = tmp_dir.name


class TestExecutorBase(unittest.TestCase):

    def test_bin(self):
        exe = Executor(bin="python /var/pybioas/manage.py")
        self.assertListEqual(exe.bin, ['python', '/var/pybioas/manage.py'])

    def test_empty_bin(self):
        exe = Executor()
        self.assertListEqual(exe.bin, [])

    @mock.patch('pybioas.scheduler.executors.shlex', autospec=True)
    def test_options(self, mock_shlex):
        mock_shlex.split.return_value = [mock.sentinel.token]
        option = mock.create_autospec(CommandOption)
        option.name = mock.sentinel.option_name
        option.get_cmd_option.return_value = mock.sentinel.cmd_option

        exe = Executor(options=[option])
        options_cmd = exe.get_options({
            mock.sentinel.option_name: mock.sentinel.option_val
        })

        option.get_cmd_option.assert_called_with(mock.sentinel.option_val)
        mock_shlex.split.assert_called_with(mock.sentinel.cmd_option)
        self.assertListEqual(options_cmd, [mock.sentinel.token])

    def test_qargs(self):
        exe = Executor(qargs=mock.sentinel.qargs)
        self.assertEqual(exe.qargs, mock.sentinel.qargs)

    def test_empty_qargs(self):
        exe = Executor()
        self.assertListEqual(exe.qargs, [])

    def test_env(self):
        exe = Executor(env=mock.sentinel.env)
        self.assertEqual(exe.env, mock.sentinel.env)

    def test_empty_env(self):
        exe = Executor()
        self.assertDictEqual(exe.env, {})


class TestExecutorOptions(unittest.TestCase):

    def test_single_option(self):
        exe = Executor(options=[CommandOption('alpha', '${value}')])
        cmd = exe.get_options({'alpha': 'foo'})
        self.assertListEqual(['foo'], cmd)

    def test_option_with_space(self):
        exe = Executor(options=[CommandOption('alpha', '${value}')])
        cmd = exe.get_options({'alpha': 'foo bar'})
        self.assertListEqual(['foo bar'], cmd)

    def test_equal_separated_option(self):
        exe = Executor(options=[CommandOption('alpha', '-a=${value}')])
        cmd = exe.get_options({'alpha': 'foo'})
        self.assertListEqual(['-a=foo'], cmd)

    def test_equal_separated_option_with_space(self):
        exe = Executor(options=[CommandOption('alpha', '-a=${value}')])
        cmd = exe.get_options({'alpha': 'foo bar'})
        self.assertListEqual(['-a=foo bar'], cmd)

    def test_multiple_arguments(self):
        exe = Executor(
            options=[
                CommandOption('alpha', 'foo', default=True),
                CommandOption('beta', 'boo', default=True),
                CommandOption('gamma', '${value}'),
                CommandOption('delta', '${value}')
            ]
        )
        cmd = exe.get_options({'gamma': 'goo', 'delta': 'doo doom'})
        self.assertListEqual(['foo', 'boo', 'goo', 'doo doom'], cmd)

    def test_split_flag(self):
        exe = Executor(
            options=[CommandOption('alpha', 'foo bar', default=True)]
        )
        cmd = exe.get_options({})
        self.assertListEqual(['foo', 'bar'], cmd)

    def test_skip_empty_arguments(self):
        exe = Executor(options=[CommandOption('alpha', '')])
        cmd = exe.get_options({})
        self.assertListEqual([], cmd)


# noinspection PyUnusedLocal
@mock.patch('pybioas.scheduler.executors.Executor.submit')
@mock.patch('pybioas.scheduler.executors.Executor.get_job_cls')
@mock.patch('pybioas.scheduler.executors.pybioas.settings', new=settings_mock)
class TestExecutorSubmit(unittest.TestCase):

    def test_submit_called(self, mock_get_job, mock_submit):
        exe = Executor()
        exe(mock.sentinel.values)
        mock_submit.assert_called_once_with(mock.sentinel.values, mock.ANY)

    def test_submit_cwd(self, mock_get_job, mock_submit):
        exe = Executor()
        exe(mock.sentinel.values)
        ((val, cwd), kwargs) = mock_submit.call_args
        self.assertTrue(cwd.startswith(tmp_dir.name))

    def test_job_created(self, mock_get_job, mock_submit):
        exe = Executor()
        job = exe(mock.sentinel.values)
        mock_job = mock_get_job.return_value.return_value
        self.assertEqual(job, mock_job)

    def test_job_args(self, mock_get_job, mock_submit):
        mock_submit.return_value = mock.sentinel.job_id
        exe = Executor()
        exe(mock.sentinel.values)
        mock_job = mock_get_job.return_value
        mock_job.assert_called_once_with(mock.sentinel.job_id, mock.ANY, exe)


class TestJob(unittest.TestCase):

    # noinspection PyUnresolvedReferences
    def setUp(self):
        self.mock_exe = mock.create_autospec(Executor)

    def test_status_property(self):
        job = Job(mock.sentinel.id, None, self.mock_exe)
        with mock.patch.object(job, 'get_status') as mock_get_status:
            mock_get_status.return_value = mock.sentinel.status
            self.assertEqual(job.status, mock.sentinel.status)
            mock_get_status.assert_called_once_with(mock.sentinel.id)

    def test_result_property(self):
        job = Job(mock.sentinel.id, None, self.mock_exe)
        with mock.patch.object(job, 'get_result') as mock_get_result:
            mock_get_result.return_value = mock.sentinel.result
            self.assertEqual(job.result, mock.sentinel.result)
            mock_get_result.assert_called_once_with(mock.sentinel.id)

    def test_file_results(self):
        mock_file_result1 = mock.create_autospec(FileResult)
        mock_file_result1.get_paths.return_value = ['/foo', '/bar']
        mock_file_result2 = mock.create_autospec(FileResult)
        mock_file_result2.get_paths.return_value = ['/qux']
        self.mock_exe.file_results = [mock_file_result1, mock_file_result2]

        job = Job(None, mock.sentinel.cwd, self.mock_exe)
        self.assertListEqual(job.file_results, ['/foo', '/bar', '/qux'])
        mock_file_result1.get_paths.assert_called_once_with(mock.sentinel.cwd)
        mock_file_result2.get_paths.assert_called_once_with(mock.sentinel.cwd)
