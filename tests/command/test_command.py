import subprocess
import tempfile
import unittest

from pybioas.scheduler.command import CommandOption, LocalCommand, ProcessOutput

try:
    import unittest.mock as mock
except ImportError:
    import mock

mock.patch.object = mock.patch.object


class TestGetFullCommandBinary(unittest.TestCase):
    """
    Group of test checking if the command line is constructed properly.
    Test if the binary executable string is properly converted into the list
    of arguments.
    """

    def test_bare_bin(self):
        """
        Tests if a single command is properly parsed to an arguments list.
        """
        cmd_cls = get_command_cls('echo')
        cmd = cmd_cls()
        self.assertListEqual(['echo'], cmd.get_full_cmd())

    def test_bin_with_arg(self):
        """
        Tests if a constant argument is passed as a second command line arg.
        """
        cmd_cls = get_command_cls('echo start')
        cmd = cmd_cls()
        self.assertListEqual(['echo', 'start'], cmd.get_full_cmd())

    def test_posix_path(self):
        """
        Tests id posix paths which doesn't contain spaces are preserved.
        """
        cmd_cls = get_command_cls('/bin/python3/python')
        cmd = cmd_cls()
        self.assertListEqual(['/bin/python3/python'], cmd.get_full_cmd())

    def test_windows_path_escaped(self):
        """
        Tests if windows path with escaped backslashes is not split.
        """
        cmd_cls = get_command_cls(r'C:\\User\\warownia1')
        cmd = cmd_cls()
        self.assertListEqual([r'C:\User\warownia1'], cmd.get_full_cmd())

    def test_windows_path_quoted(self):
        """
        Tests if windows path with quoted backslashes is not split.
        """
        cmd_cls = get_command_cls(r'"C:\User\warownia1"')
        cmd = cmd_cls()
        self.assertListEqual([r'C:\User\warownia1'], cmd.get_full_cmd())

    def test_path_with_excaped_space(self):
        """
        Tests if path with escaped spaces is not split.
        """
        cmd_cls = get_command_cls('/home/super\ user/')
        cmd = cmd_cls()
        self.assertListEqual(['/home/super user/'], cmd.get_full_cmd())

    def test_path_with_quoted_space(self):
        """
        Tests if path with quoted spaces is not split.
        """
        cmd_cls = get_command_cls('"/home/super user/"')
        cmd = cmd_cls()
        self.assertListEqual(['/home/super user/'], cmd.get_full_cmd())


class TestGetFullCommandOptions(unittest.TestCase):
    """
    Group of tests checking if the command line options are correctly passed
    to the command line.
    Checks for replacement of template placeholders, proper character escaping,
    and preserving options order.
    """

    def test_single_option(self):
        """
        Tests if a single option `foo` is properly parsed and makes a
        separate command argument `'foo'`
        """
        cmd_cls = get_command_cls(
            'echo',
            [CommandOption('alpha', '${value}')]
        )
        cmd = cmd_cls({'alpha': 'foo'})
        self.assertListEqual(['echo', 'foo'], cmd.get_full_cmd())

    def test_option_with_space(self):
        """
        Tests if the value containing space `foo bar` will be passed as a
        single command argument `'foo bar'`
        """
        cmd_cls = get_command_cls(
            'echo',
            [CommandOption('alpha', '${value}')]
        )
        cmd = cmd_cls({'alpha': 'foo bar'})
        self.assertListEqual(['echo', 'foo bar'], cmd.get_full_cmd())

    def test_equal_separated_option(self):
        """
        Tests if the options with equal sign `-a=foo` are passed as a single
        command argument `'-a=foo'`
        """
        cmd_cls = get_command_cls(
            'echo',
            [CommandOption('alpha', '-a=${value}')]
        )
        cmd = cmd_cls({'alpha': 'foo'})
        self.assertListEqual(['echo', '-a=foo'], cmd.get_full_cmd())

    def test_equal_separated_option_with_space(self):
        """
        Tests if the option `-a="foo bar"` will be passed as a single
        command argument `'-a=foo bar'`
        """
        cmd_cls = get_command_cls(
            'echo',
            [CommandOption('alpha', '-a=${value}')]
        )
        cmd = cmd_cls({'alpha': 'foo bar'})
        self.assertListEqual(['echo', '-a=foo bar'], cmd.get_full_cmd())

    def test_multiple_arguments(self):
        """
        Tests if mutltiple arguments are properly passed to the list.
        """
        cmd_cls = get_command_cls(
            'echo',
            [
                CommandOption('alpha', 'foo', default=True),
                CommandOption('beta', 'boo', default=True),
                CommandOption('gamma', '${value}'),
                CommandOption('delta', '${value}')
            ]
        )
        cmd = cmd_cls({'gamma': 'goo', 'delta': 'doo doom'})
        self.assertListEqual(
            ['echo', 'foo', 'boo', 'goo', 'doo doom'],
            cmd.get_full_cmd()
        )

    def test_split_flag(self):
        """
        Tests if the flag split into two arguments `"foo bar"` is passed as
        two arguments `'foo', 'bar'`.
        """
        cmd_cls = get_command_cls(
            'echo',
            [CommandOption('alpha', 'foo bar', default=True)]
        )
        cmd = cmd_cls()
        self.assertListEqual(['echo', 'foo', 'bar'], cmd.get_full_cmd())

    def test_skip_empty_arguments(self):
        """
        Tests if empty arguments are skipped.
        """
        cmd_cls = get_command_cls('echo', [CommandOption('alpha', '')])
        cmd = cmd_cls()
        self.assertListEqual(['echo'], cmd.get_full_cmd())


# noinspection PyUnusedLocal
@mock.patch('pybioas.scheduler.command.subprocess', autospec=True)
class TestCommandExecution(unittest.TestCase):

    def setUp(self):
        self.settings_patch = mock.patch('pybioas.settings')
        mock_settings = self.settings_patch.start()
        self.cwd = tempfile.TemporaryDirectory()
        mock_settings.WORK_DIR = self.cwd.name

    def tearDown(self):
        self.settings_patch.stop()
        self.cwd.cleanup()

    def test_command_execution(self, mock_subprocess):
        """
        Tests if a subprocess.Popen function is correctly called by the
        command object and compares the return value.
        """
        mock_process = mock.create_autospec(subprocess.Popen)
        mock_subprocess.Popen.return_value = mock_process
        mock_subprocess.PIPE = mock.sentinel.PIPE
        mock_process.communicate.return_value = (b'foofoo', b'barbazquz')
        mock_process.returncode = mock.sentinel.returncode

        command = LocalCommand()
        with mock.patch.object(command, 'get_full_cmd') as mock_get_cmd:
            mock_get_cmd.return_value = mock.sentinel.cmd
            ret = command.run_command()  # type: ProcessOutput

        mock_subprocess.Popen.assert_called_once_with(
            mock.sentinel.cmd,
            stdout=mock.sentinel.PIPE,
            stderr=mock.sentinel.PIPE,
            env=mock.ANY,
            cwd=mock.ANY
        )
        self.assertEqual(ret.return_code, mock.sentinel.returncode)
        self.assertEqual(ret.stdout, 'foofoo')
        self.assertEqual(ret.stderr, 'barbazquz')
        self.assertEqual(ret.files, [])

    def test_missing_bin(self, mock_subprocess):
        """
        Checks if AttributeError is raised for missing _bin attribute
        """
        command = LocalCommand()
        command._options = []
        with self.assertRaises(AttributeError):
            command.run_command()

    def test_missing_options(self, mock_subprocess):
        """
        Checks if AttributeError is raised for missing _options attribute
        """
        command = LocalCommand()
        command._binary = 'echo'
        with self.assertRaises(AttributeError):
            command.run_command()

    def test_no_missing_attributes(self, mock_subprocess):
        """
        Tests if filling _bin and _options attributes is enough for the
        command to be built and tun.
        """
        mock_process = mock_subprocess.Popen.return_value
        mock_subprocess.PIPE = mock.sentinel.PIPE
        mock_process.returncode = mock.sentinel.returncode
        mock_process.communicate.return_value = (b'', b'')

        command = LocalCommand()
        command._options = []
        command._binary = ''
        ret_value = command.run_command()

        self.assertEqual(mock_subprocess.Popen.call_count, 1)
        self.assertIsNotNone(ret_value)


def get_command_cls(binary='echo', options=list()):
    """
    Helper function which creates a TestCommand class
    :param binary: executable command
    :param options: list of options passed to the command
    :type options: list[CommandOption]
    :return: LocalCommand subclass
    :rtype: type[LocalCommand]
    """
    return type(
        'TestCommand',
        (LocalCommand,),
        {
            "_binary": binary,
            "_options": options,
            "_output_files": [],
            "_env": None
        }
    )
