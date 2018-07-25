import os
import unittest
import mock

import slivka.scheduler.execution_manager as execution_manager
from slivka.scheduler.execution_manager import CommandOption, RunConfiguration


# noinspection PyTypeChecker
class TestArgumentBuilder(unittest.TestCase):

    class DummyRunner(execution_manager.Runner):
        def submit(self):
            return mock.MagicMock()

        @classmethod
        def get_job_handler_class(cls):
            return mock.MagicMock()

    def setUp(self):
        self.factory = mock.MagicMock(spec=execution_manager.RunnerFactory)
        self.configuration = \
            RunConfiguration('dummy', self.DummyRunner, 'dummy.exe', [], {})

    def test_plain_args(self):
        self.factory.options = [
            CommandOption('foo', '-f=${value}', None),
            CommandOption('bar', '--bar=${value}', None),
            CommandOption('qux', '-q=${value}', '10')
        ]
        values = {'foo': 'v1', 'bar': 'v2', 'qux': 'v3'}
        runner = self.DummyRunner(
            self.factory, self.configuration, values, '/home'
        )
        result = ['-f=v1', '--bar=v2', '-q=v3']
        self.assertListEqual(runner.args, result)

    def test_parameter_with_space(self):
        self.factory.options = [CommandOption('foo', '-f ${value}', None)]
        values = {'foo': 'v1'}
        runner = self.DummyRunner(
            self.factory, self.configuration, values, '/home'
        )
        self.assertListEqual(runner.args, ['-f', 'v1'])

    def test_value_with_space(self):
        self.factory.options = [CommandOption('foo', '-f=${value}', None)]
        values = {'foo': 'v1 v1'}
        runner = self.DummyRunner(
            self.factory, self.configuration, values, '/home'
        )
        self.assertListEqual(runner.args, ['-f=v1 v1'])

    def test_missing_skipped(self):
        self.factory.options = [
            CommandOption('foo', '-f=${value}', None),
            CommandOption('bar', '-b=${value}', None)
        ]
        values = {'bar': 'v1'}
        runner = self.DummyRunner(
            self.factory, self.configuration, values, '/home'
        )
        self.assertListEqual(runner.args, ['-b=v1'])

    def test_null_skipped(self):
        self.factory.options = [
            CommandOption('foo', '-f=${value}', None),
            CommandOption('bar', '-b=${value}', None)
        ]
        values = {
            'foo': None,
            'bar': 'v1'
        }
        runner = self.DummyRunner(
            self.factory, self.configuration, values, '/home'
        )
        self.assertListEqual(runner.args, ['-b=v1'])

    def test_default(self):
        self.factory.options = [CommandOption('foo', '-f=${value}', 'v')]
        runner = self.DummyRunner(
            self.factory, self.configuration, {}, '/home'
        )
        self.assertListEqual(runner.args, ['-f=v'])

    def test_default_override_empty(self):
        self.factory.options = [CommandOption('foo', '-f=${value}', 'v')]
        runner = self.DummyRunner(
            self.factory, self.configuration, {'foo': 'f'}, '/home'
        )
        self.assertListEqual(runner.args, ['-f=f'])

    def test_default_override_null(self):
        self.factory.options = [
            CommandOption('foo', '-f=${value}', 'v')
        ]
        runner = self.DummyRunner(
            self.factory, self.configuration, {'foo': None}, '/home'
        )
        self.assertListEqual(runner.args, ['-f=v'])


# noinspection PyTypeChecker
class TestFileArgument(unittest.TestCase):

    class DummyRunner(execution_manager.Runner):
        def submit(self):
            return mock.MagicMock()

        @classmethod
        def get_job_handler_class(cls):
            return mock.MagicMock()

    def setUp(self):
        self.factory = mock.MagicMock(spec=execution_manager.RunnerFactory)
        self.configuration = RunConfiguration(
            'dummy', self.DummyRunner, 'dummy.exe', [], {}
        )

    def test_simple_filename(self):
        self.factory.options = [
            CommandOption('foo', '-f=${file:input.txt}', None)
        ]
        values = {
            'foo': '/home/slivka/inputfile.in'
        }
        runner = self.DummyRunner(
            self.factory, self.configuration, values, '/home'
        )
        self.assertListEqual(runner.args, ['-f=input.txt'])

    def test_file_with_space(self):
        self.factory.options = [
            CommandOption('foo', '-f=${file:in put.txt}', None)
        ]
        values = {
            'foo': '/home/slivka/inputfile.in'
        }
        runner = self.DummyRunner(
            self.factory, self.configuration, values, '/home'
        )
        self.assertListEqual(runner.args, ['-f=in put.txt'])

    def test_file_in_folder(self):
        self.factory.options = [
            CommandOption('foo', '-f=${file:result/input.txt}', None)
        ]
        values = {'foo': '/home/slivka/input.in'}
        runner = self.DummyRunner(
            self.factory, self.configuration, values, '/home'
        )
        self.assertListEqual(runner.args, ['-f=result/input.txt'])

    def test_file_outside_cwd(self):
        self.factory.options = [
            CommandOption('foo', '-f=${file:../input.txt}', None)
        ]
        values = {'foo': '/home/slivka/input.in'}
        with self.assertRaises(ValueError):
            self.DummyRunner(
                self.factory, self.configuration, values, '/home'
            )


class TestPrepareRunner(unittest.TestCase):

    class DummyRunner(execution_manager.Runner):
        def submit(self):
            return mock.MagicMock()

        @classmethod
        def get_job_handler_class(cls):
            return mock.MagicMock()

    def setUp(self):
        self.factory = mock.MagicMock(spec=execution_manager.RunnerFactory)
        self.configuration = RunConfiguration(
            'dummy', self.DummyRunner, 'dummy.exe', [], {}
        )

    @mock.patch('slivka.scheduler.execution_manager.os.mkdir')
    @mock.patch('slivka.scheduler.execution_manager.os.path.isdir')
    def test_create_cwd(self, mock_isdir, mock_mkdir):
        self.factory.options = []
        runner = self.DummyRunner(
            self.factory, self.configuration, {}, '/home/workDir'
        )
        mock_isdir.return_value = False
        runner.prepare()
        cwd = os.path.normpath('/home/workDir')
        mock_isdir.assert_called_with(cwd)
        mock_mkdir.assert_called_once_with(cwd)

    @mock.patch('slivka.scheduler.execution_manager.os.mkdir')
    @mock.patch('slivka.scheduler.execution_manager.os.path.isdir')
    def test_existing_cwd(self, mock_isdir, mock_mkdir):
        self.factory.options = []
        runner = self.DummyRunner(
            self.factory, self.configuration, {}, '/home/workDir'
        )
        mock_isdir.return_value = True
        runner.prepare()
        mock_isdir.assert_called_once_with(os.path.normpath('/home/workDir'))
        mock_mkdir.assert_not_called()

    @mock.patch('slivka.scheduler.execution_manager.os.link')
    @mock.patch('slivka.scheduler.execution_manager.os.path.isdir')
    def test_link(self, mock_isdir, mock_link):
        self.factory.options = [
            CommandOption('foo', '-f=${file:input.txt}', None)
        ]
        values = {'foo': '/home/slivka/inputs/file.in'}
        runner = self.DummyRunner(
            self.factory, self.configuration, values, '/home/workDir'
        )
        mock_isdir.return_value = True
        with mock.patch('slivka.scheduler.execution_manager.os.mkdir'):
            runner.prepare()
        mock_link.assert_called_once_with(
            os.path.normpath('/home/slivka/inputs/file.in'),
            os.path.normpath(os.path.join('/home/workDir', 'input.txt'))
        )
