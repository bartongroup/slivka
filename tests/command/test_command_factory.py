import os
import shlex
import unittest

try:
    import unittest.mock as mock
except ImportError:
    import mock

from pybioas.scheduler.command import CommandOption, FileOutput, \
    PatternFileOutput, CommandFactory

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
        self.assertFalse(cmd)

    def test_no_value_2(self):
        option = CommandOption('', '-foo')
        cmd = option.get_cmd_option(None)
        self.assertFalse(cmd)

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
    def test_single_file(self):
        fo = FileOutput('somefile.txt')
        files = fo.get_files_paths('/var/')
        self.assertListEqual(files, ['/var/somefile.txt'])

    @unittest.skipUnless(os.name == 'nt', "Windows paths only.")
    def test_single_file(self):
        fo = FileOutput('somefile.txt')
        files = fo.get_files_paths('C:\\var\\')
        self.assertListEqual(files, ['C:\\var\\somefile.txt'])

    @unittest.skipUnless(os.name == 'posix', "POSIX paths only.")
    @mock.patch("pybioas.scheduler.command.os.listdir")
    def test_pattern_file(self, mock_listdir):
        """
        :type mock_listdir: mock.MagicMock
        """
        mock_listdir.return_value = ["file1.txt", "file2.txt", "donttouch.me"]
        fo = PatternFileOutput(r'.+\.txt')
        files = fo.get_files_paths('/var/')
        self.assertListEqual(files, ["/var/file1.txt", "/var/file2.txt"])

    @unittest.skipUnless(os.name == 'nt', "Windows paths only.")
    @mock.patch("pybioas.scheduler.command.os.listdir")
    def test_pattern_file(self, mock_listdir):
        """
        :type mock_listdir: mock.MagicMock
        """
        mock_listdir.return_value = ["file1.txt", "file2.txt", "donttouch.me"]
        fo = PatternFileOutput(r'.+\.txt')
        files = fo.get_files_paths('C:\\var\\')
        self.assertListEqual(
            files, ["C:\\var\\file1.txt", "C:\\var\\file2.txt"]
        )

    def test_single_file_path_abs(self):
        fo = FileOutput('somefile.txt')
        files = fo.get_files_paths(os.curdir)
        for path in files:
            self.assertTrue(os.path.isabs(path))

    @mock.patch("pybioas.scheduler.command.os.listdir")
    def test_pattern_file_path_abs(self, mock_listdir):
        mock_listdir.return_value = ["file1.txt", "file2.txt", "donttouch.me"]
        fo = PatternFileOutput(r'.+\.txt')
        files = fo.get_files_paths(os.curdir)
        for path in files:
            self.assertTrue(os.path.isabs(path))


class TestCommandFactory(unittest.TestCase):

    def setUp(self):
        self.open_patch = mock.patch(
            'pybioas.scheduler.command.open',
            mock.MagicMock(side_effect=mock_open)
        )
        self.open_patch.start()
        self.factory = CommandFactory('data/fake_config.ini')

    def tearDown(self):
        self.open_patch.stop()

    def test_configurations_list(self):
        self.assertSetEqual(
            set(self.factory.configurations),
            {'Fake', 'Dummy'}
        )

    def test_env_setting(self):
        Dummy = self.factory.get_command_class('Dummy')
        self.assertDictEqual(
            Dummy._env,
            {
                'MYDUMMYENV': 'Dummy env',
                'THEIRDUMMYENV': 'Another env',
                'YOURDUMMYENV': 'One more env'
            }
        )

    def test_bin_setting(self):
        Fake = self.factory.get_command_class('Fake')
        self.assertEqual(Fake._binary, 'fake_executable')

    def test_options(self):
        Fake = self.factory.get_command_class('Fake')

        option = next((opt for opt in Fake._options if opt.name == 'alpha'))
        self.assertEqual(option._param_template.template, '-a ${value}')
        self.assertEqual(option._default, 'foo')

        option = next((opt for opt in Fake._options if opt.name == 'beta'))
        self.assertEqual(option._param_template.template, '--beta=${value}')
        self.assertIsNone(option._default)

    def test_pattern_output(self):
        Fake = self.factory.get_command_class('Fake')
        output = Fake._output_files[0]
        self.assertIsInstance(output, PatternFileOutput)
        self.assertEqual(output._regex.pattern, ".+\\.txt")

    def test_param_output(self):
        Fake = self.factory.get_command_class('Fake')
        output = Fake._output_files[1]
        self.assertIsInstance(output, FileOutput)
        option = next((opt for opt in Fake._options
                       if opt.name == '--out ${value}'))
        self.assertEqual(option._param_template.template, '--out ${value}')
        self.assertEqual(option._default, output._name)
