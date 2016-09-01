import os
import shlex
import unittest

try:
    import unittest.mock as mock
except ImportError:
    import mock

from slivka.scheduler.command import (
    CommandOption, PathWrapper, PatternPathWrapper
)

THIS_FOLDER = os.path.abspath(os.path.dirname(__file__))


def mock_open(filename):
    with open(os.path.join(THIS_FOLDER, filename)) as file:
        content = file.read()
    file_object = mock.mock_open(read_data=content).return_value
    file_object.__iter__.return_value = content.splitlines(True)
    return file_object


class TestCommandOptionBase(unittest.TestCase):

    def test_placeholder(self):
        option = CommandOption('', '-foo ${value}')
        cmd = option.get_cmd_option('bar')
        self.assertEqual(cmd, '-foo bar')

    def test_no_placeholder(self):
        option = CommandOption('', '-foo')
        cmd = option.get_cmd_option('foobar')
        self.assertEqual(cmd, '-foo')

    def test_no_value_1(self):
        option = CommandOption('', '-foo ${value}')
        cmd = option.get_cmd_option(None)
        self.assertIsNone(cmd)

    def test_no_value_2(self):
        option = CommandOption('', '-foo')
        cmd = option.get_cmd_option(None)
        self.assertIsNone(cmd)

    def test_empty_string(self):
        option = CommandOption('', '-foo ${value}')
        cmd = option.get_cmd_option('')
        chunks = shlex.split(cmd)
        self.assertListEqual(chunks, ['-foo', ''])


class TestCommandOptionDefault(unittest.TestCase):

    def setUp(self):
        self.option = CommandOption('', '${value}', default='abc')

    def test_default_not_used(self):
        cmd = self.option.get_cmd_option('def')
        self.assertEqual(cmd, 'def')

    def test_default_used(self):
        cmd = self.option.get_cmd_option(None)
        self.assertEqual(cmd, 'abc')


class TestCommandOptionEscaping(unittest.TestCase):

    def setUp(self):
        self.option = CommandOption('', '-foo ${value}')

    def test_quote_space(self):
        self.check_argument('hello world')

    def test_escape_backslash(self):
        self.check_argument(r'hello\world')

    def test_escape_slash(self):
        self.check_argument('hello/world')

    def test_escape_single_quote(self):
        self.check_argument("isn't")

    def test_escape_quote(self):
        self.check_argument('"hello"')

    def check_argument(self, value):
        cmd = self.option.get_cmd_option(value)
        chunks = shlex.split(cmd)
        self.assertListEqual(chunks, ['-foo', value])


class TestFileOutputs(unittest.TestCase):

    @unittest.skipUnless(os.name == 'posix', "POSIX paths only.")
    @mock.patch("slivka.scheduler.command.os.path.exists")
    def test_single_file(self, mock_pathexist):
        mock_pathexist.return_value = True
        fo = PathWrapper('somefile.txt')
        files = fo.get_paths('/var/')
        self.assertListEqual(files, ['/var/somefile.txt'])

    @unittest.skipUnless(os.name == 'nt', "Windows paths only.")
    @mock.patch("slivka.scheduler.command.os.path.exists")
    def test_single_file(self, mock_pathexist):
        mock_pathexist.return_value = True
        fo = PathWrapper('somefile.txt')
        files = fo.get_paths('C:\\var\\')
        self.assertListEqual(files, ['C:\\var\\somefile.txt'])

    @unittest.skipUnless(os.name == 'posix', "POSIX paths only.")
    @mock.patch("slivka.scheduler.command.os.listdir")
    def test_pattern_file(self, mock_listdir):
        """
        :type mock_listdir: mock.MagicMock
        """
        mock_listdir.return_value = ["file1.txt", "file2.txt", "donttouch.me"]
        fo = PatternPathWrapper(r'.+\.txt')
        files = fo.get_paths('/var/')
        self.assertListEqual(files, ["/var/file1.txt", "/var/file2.txt"])

    @unittest.skipUnless(os.name == 'nt', "Windows paths only.")
    @mock.patch("slivka.scheduler.command.os.listdir")
    def test_pattern_file(self, mock_listdir):
        """
        :type mock_listdir: mock.MagicMock
        """
        mock_listdir.return_value = ["file1.txt", "file2.txt", "donttouch.me"]
        fo = PatternPathWrapper(r'.+\.txt')
        files = fo.get_paths('C:\\var\\')
        self.assertListEqual(
            files, ["C:\\var\\file1.txt", "C:\\var\\file2.txt"]
        )

    def test_single_file_path_abs(self):
        fo = PathWrapper('somefile.txt')
        files = fo.get_paths(os.curdir)
        for path in files:
            self.assertTrue(os.path.isabs(path))

    @mock.patch("slivka.scheduler.command.os.listdir")
    def test_pattern_file_path_abs(self, mock_listdir):
        mock_listdir.return_value = ["file1.txt", "file2.txt", "donttouch.me"]
        fo = PatternPathWrapper(r'.+\.txt')
        files = fo.get_paths(os.curdir)
        for path in files:
            self.assertTrue(os.path.isabs(path))
