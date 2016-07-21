import unittest

from pybioas.scheduler.command.command_factory import CommandOption
from pybioas.scheduler.command.local_command import LocalCommand


class TestGetFullCommandBinary(unittest.TestCase):
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

    def test_windows_path(self):
        """
        Tests if windows path with escaped or quoted backslashes is properly
        parsed.
        """
        cmd_cls = get_command_cls(r'C:\\User\\warownia1')
        cmd = cmd_cls()
        self.assertListEqual([r'C:\User\warownia1'], cmd.get_full_cmd())

        cmd_cls = get_command_cls(r'"C:\User\warownia1"')
        cmd = cmd_cls()
        self.assertListEqual([r'C:\User\warownia1'], cmd.get_full_cmd())

    def test_path_with_space(self):
        """
        Tests if path with escaped or quoted spaces is properly parsed.
        """
        cmd_cls = get_command_cls('/home/super\ user/')
        cmd = cmd_cls()
        self.assertListEqual(['/home/super user/'], cmd.get_full_cmd())

        cmd_cls = get_command_cls('"/home/super user/"')
        cmd = cmd_cls()
        self.assertListEqual(['/home/super user/'], cmd.get_full_cmd())


class TestGetFullCommandOptions(unittest.TestCase):
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
        Tests if mutliple arguments are properly passed to the list.
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


def get_command_cls(binary='echo', options=list()):
    """
    Helper function which creates a TestCommand class
    :param binary: executable command
    :param options: list of options passed to the command
    :type options: list[CommandOption]
    :return: LocalCommand subclass
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
