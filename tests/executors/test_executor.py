import tempfile
import unittest

from pybioas.scheduler.command import CommandOption, PathWrapper
from pybioas.scheduler.exc import QueueUnavailableError, QueueBrokenError, \
    JobNotFoundError
from pybioas.scheduler.executors import Executor, Job, GridEngineExec, \
    GridEngineJob

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

    def test_queue_unavailable(self, mock_get_job, mock_submit):
        mock_submit.side_effect = QueueUnavailableError(mock.sentinel.msg)
        exe = Executor()
        with self.assertRaises(QueueUnavailableError) as cm:
            exe(mock.sentinel.values)
            self.assertTupleEqual(cm.exception.args, (mock.sentinel.msg,))

    def test_queue_broken(self, mock_get_job, mock_submit):
        mock_submit.side_effect = QueueBrokenError(mock.sentinel.msg)
        exe = Executor()
        with self.assertRaises(QueueBrokenError) as cm:
            exe(mock.sentinel.values)
            self.assertTupleEqual(cm.exception.args, (mock.sentinel.msg,))

    def test_job_not_found(self, mock_get_job, mock_submit):
        mock_submit.side_effect = JobNotFoundError(mock.sentinel.msg)
        exe = Executor()
        with self.assertRaises(JobNotFoundError) as cm:
            exe(mock.sentinel.values)
            self.assertTupleEqual(cm.exception.args, (mock.sentinel.msg,))

    def test_unexpected_queue_error(self, mock_get_job, mock_submit):
        mock_submit.side_effect = Exception
        exe = Executor()
        self.assertRaises(QueueBrokenError, exe, mock.sentinel.values)


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
        with mock.patch.object(job, 'get_result') as mock_get_result, \
                mock.patch.object(job, 'get_status',
                                  return_value=Job.STATUS_COMPLETED):
            mock_get_result.return_value = mock.sentinel.result
            self.assertEqual(job.result, mock.sentinel.result)
            mock_get_result.assert_called_once_with(mock.sentinel.id)

    def test_file_results(self):
        mock_file_result1 = mock.create_autospec(PathWrapper)
        mock_file_result1.get_paths.return_value = ['/foo', '/bar']
        mock_file_result2 = mock.create_autospec(PathWrapper)
        mock_file_result2.get_paths.return_value = ['/qux']
        self.mock_exe.result_paths = [mock_file_result1, mock_file_result2]

        job = Job(None, mock.sentinel.cwd, self.mock_exe)
        self.assertListEqual(job.result_paths, ['/foo', '/bar', '/qux'])
        mock_file_result1.get_paths.assert_called_once_with(mock.sentinel.cwd)
        mock_file_result2.get_paths.assert_called_once_with(mock.sentinel.cwd)


class TestGridEngineExec(unittest.TestCase):

    def setUp(self):
        self.subprocess_path = mock.patch(
            'pybioas.scheduler.executors.subprocess'
        )
        self.mock_subprocess = self.subprocess_path.start()
        self.mock_popen = self.mock_subprocess.Popen.return_value
        self.mock_popen.communicate.return_value = (
            'Your job 0 (command) has been submitted', ''
        )
        self.exe = GridEngineExec()

    def tearDown(self):
        self.subprocess_path.stop()

    @mock.patch('pybioas.scheduler.executors.Executor.qargs',
                new_callable=mock.PropertyMock)
    def test_qsub(self, mock_qargs):
        mock_qargs.return_value = [mock.sentinel.qarg1, mock.sentinel.qarg2]
        self.exe.submit({}, '')
        expected_arg = ([
            'qsub', '-cwd', '-e', 'stderr.txt', '-o', 'stdout.txt',
            mock.sentinel.qarg1, mock.sentinel.qarg2
        ],)
        (args, kwargs) = self.mock_subprocess.Popen.call_args
        self.assertTupleEqual(args, expected_arg)

    @mock.patch('pybioas.scheduler.executors.Executor.bin',
                new_callable=mock.PropertyMock)
    def test_command(self, mock_bin):
        mock_bin.return_value = ['mockpython', 'mockscript.py']
        self.exe.submit({}, '')
        self.mock_popen.communicate.assert_called_once_with(
            "echo > started;\n"
            "mockpython mockscript.py;\n"
            "echo > finished;"
        )

    def test_job_id(self):
        self.mock_popen.communicate.return_value = (
            'Your job 4365 (command) has been submitted', ''
        )
        job_id = self.exe.submit({}, '')
        self.assertEqual(job_id, "4365")


class TestGridEngineJob(unittest.TestCase):

    qstat_output = (
        "1771701 1.00500 jp_4NIaEBc mockuser     r     "
        "08/13/2016 17:57:21 c6100.q@c6100-1-4.cluster.life     4\n"
        "1778095 1.00500 jp_D21Nm6a mockuser     r     "
        "08/15/2016 22:53:29 c6100.q@c6100-1-4.cluster.life     4\n"
        "1791672 0.01993 R          mockuser     Eqw   "
        "08/17/2016 17:41:34                                    1\n"
        "1776414 0.00588 fic_Sample mockuser     qw    "
        "08/15/2016 11:44:23                                   10\n"
        "1776413 0.00589 fic_Sample mockuser     d     "
        "08/15/2016 11:44:23                                   10\n"
    )

    def setUp(self):
        self.getuser_patch = mock.patch(
            'pybioas.scheduler.executors.getpass.getuser',
            return_value='mockuser'
        )
        self.getuser_patch.start()
        self.subprocess_patch = mock.patch(
            'pybioas.scheduler.executors.subprocess',
            autospec=True
        )
        self.mock_subprocess = self.subprocess_patch.start()
        mock_popen = self.mock_subprocess.Popen.return_value
        mock_popen.communicate.return_value = (self.qstat_output, '')
        mock_exec = mock.create_autospec(Executor)
        mock_exec.result_paths = []
        self.job = GridEngineJob('', '', mock_exec)

    def tearDown(self):
        self.getuser_patch.stop()
        self.subprocess_patch.stop()

    @mock.patch('pybioas.scheduler.executors.os.path', autospec=True)
    def test_qstat_call(self, mock_path):
        mock_path.getmtime.return_value = 0
        self.job.get_status('abc')
        (args, kwargs) = self.mock_subprocess.Popen.call_args
        expected_args = ('qstat -u \'mockuser\'',)
        self.assertTupleEqual(args, expected_args)
        self.assertTrue(kwargs['shell'])

    def test_job_queued(self):
        status = self.job.get_status('1776414')
        self.assertEqual(status, Job.STATUS_QUEUED)

    def test_job_running(self):
        status = self.job.get_status('1778095')
        self.assertEqual(status, Job.STATUS_RUNNING)

    @mock.patch('pybioas.scheduler.executors.os.path', autospec=True)
    def test_job_completed_not_synced(self, mock_path):
        mock_path.getmtime.side_effect = (10, FileNotFoundError)
        status = self.job.get_status('1772453')
        self.assertEqual(status, Job.STATUS_RUNNING)

    @mock.patch('pybioas.scheduler.executors.os.path', autospec=True)
    def test_job_running_restarted(self, mock_path):
        mock_path.getmtime.side_effect = (20, 19)
        status = self.job.get_status('1772453')
        self.assertEqual(status, Job.STATUS_RUNNING)

    @mock.patch('pybioas.scheduler.executors.os.path', autospec=True)
    def test_job_completed(self, mock_path):
        mock_path.getmtime.side_effect = (19, 20)
        status = self.job.get_status('1772453')
        self.assertEqual(status, Job.STATUS_COMPLETED)

    def test_job_deleted(self):
        status = self.job.get_status('1776413')
        self.assertEqual(status, Job.STATUS_DELETED)
