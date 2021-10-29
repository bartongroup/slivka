import filecmp
import os
import tempfile
from unittest.mock import MagicMock

from nose.tools import assert_equal, assert_dict_equal, assert_list_equal, \
    assert_true

from conf import ServiceConfig
from scheduler.runner import Command, Job
from . import make_starter

Argument = ServiceConfig.Argument


class TestEnvironmentVariables:

    @classmethod
    def setup_class(cls):
        os.environ['SLIVKA_HOME'] = '/tmp/slivka'
        os.environ['MY_VARIABLE'] = 'some-value'

    @classmethod
    def teardown_class(cls):
        del os.environ['SLIVKA_HOME']
        del os.environ['MY_VARIABLE']

    def test_interpolation_in_variable(self):
        starter = make_starter(env={"BIN_PATH": "${SLIVKA_HOME}/bin"})
        assert_equal(starter.env["BIN_PATH"], "/tmp/slivka/bin")

    def test_variable_values(self):
        starter = make_starter(env={"BIN": "/bin"})
        assert_dict_equal(
            dict(starter.env),
            {
                "SLIVKA_HOME": "/tmp/slivka",
                "PATH": os.environ['PATH'],
                "BIN": "/bin"
            }
        )

    def test_base_command_interpolation_from_system_var(self):
        starter = make_starter(
            base_command="$SLIVKA_HOME/example.bin"
        )
        assert_list_equal(starter.base_command, ["/tmp/slivka/example.bin"])

    def test_base_command_interpolation_from_custom_var(self):
        starter = make_starter(
            base_command="$BIN/example.bin",
            env={"BIN": "/usr/bin"}
        )
        assert_list_equal(starter.base_command, ["/usr/bin/example.bin"])

    def test_nested_interpolation_in_command(self):
        starter = make_starter(
            base_command="$BIN/example.bin",
            env={"BIN": "$SLIVKA_HOME/bin"}
        )
        assert_list_equal(starter.base_command, ["/tmp/slivka/bin/example.bin"])

    def test_interpolation_in_argument(self):
        starter = make_starter(
            args=[Argument("arg", "-p=$MY_VARIABLE", default="T")]
        )
        assert_list_equal(starter.build_command_args({}), ["-p=some-value"])

    def test_variable_injection(self):
        starter = make_starter(
            args=[Argument("arg", "$(value)")],
        )
        assert_list_equal(
            starter.build_command_args({'arg': "$MY_VARIABLE"}),
            ["$MY_VARIABLE"]
        )
        assert_list_equal(
            starter.build_command_args({'arg': "${SLIVKA_HOME}"}),
            ["${SLIVKA_HOME}"]
        )


class TestBuildCommandArgs:

    @staticmethod
    def _check_args(runner, inputs, args):
        assert_list_equal(runner.build_command_args(inputs), args)

    def test_symbol_delimited_option(self):
        runner = make_starter(
            args=[Argument('myoption', '--option=$(value)')],
        )
        yield self._check_args, runner, {}, []
        yield self._check_args, runner, {'myoption': None}, []
        yield self._check_args, runner, {'myoption': ''}, ['--option=']
        yield self._check_args, runner, {'myoption': 'my value'}, ["--option=my value"]

    def test_space_delimited_option(self):
        runner = make_starter(
            args=[Argument('myoption', '--option $(value)')],
        )
        yield (self._check_args, runner,
               {'myoption': 'value'}, ['--option', 'value'])
        yield (self._check_args, runner,
               {'myoption': 'my value'}, ['--option', 'my value'])
        yield (self._check_args, runner,
               {'myoption': 'my \'fun \' value'},
               ['--option', 'my \'fun \' value'])

    def test_quoted_option(self):
        runner = make_starter(
            args=[Argument('myoption', "'--option $(value)'"),
                  Argument('otheropt', "\"--option $(value)\"")],
        )
        yield self._check_args, runner, {'myoption': 'value'}, ['--option value']
        yield self._check_args, runner, {'myoption': 'my value'}, ['--option my value']
        yield self._check_args, runner, {'otheropt': 'my value'}, ["--option my value"]
        yield (self._check_args, runner,
               {'myoption': 'my \'fun \' value'},
               ['--option my \'fun \' value'])
        yield (self._check_args, runner,
               {'otheropt': 'my \'fun \' value'},
               ['--option my \'fun \' value'])

    def test_flag_option(self):
        runner = make_starter(
            args=[Argument('myflag', "--flag")]
        )
        yield self._check_args, runner, {}, []
        yield self._check_args, runner, {'myflag': False}, []
        yield self._check_args, runner, {'myflag': None}, []
        yield self._check_args, runner, {'myflag': "true"}, ["--flag"]

    def test_default_substitution(self):
        runner = make_starter(
            args=[Argument('input', "-v=$(value)", default="default")]
        )
        yield self._check_args, runner, {'input': 'foo'}, ['-v=foo']
        yield self._check_args, runner, {'input': None}, ['-v=default']
        yield self._check_args, runner, {'input': ''}, ['-v=']
        yield self._check_args, runner, {}, ["-v=default"]

    def test_parameters_ordering(self):
        runner = make_starter(
            args=[
                Argument('iters', "--iter=$(value)"),
                Argument('outfile', "-o $(value)"),
                Argument('verbose', "-V"),
                Argument('infile', "$(value)")
            ]
        )
        yield self._check_args, runner, {}, []
        yield (
            self._check_args, runner,
            {'iters': "5", 'outfile': 'output.txt', 'verbose': "true",
             'infile': 'input.txt'},
            ['--iter=5', '-o', 'output.txt', '-V', 'input.txt']
        )
        yield (
            self._check_args, runner,
            {'iters': "3", 'verbose': False, 'infile': 'input.txt'},
            ['--iter=3', 'input.txt']
        )
        yield (
            self._check_args, runner,
            {'outfile': 'out.out', 'verbose': "true", 'iters': "10"},
            ['--iter=10', '-o', 'out.out', '-V']
        )

    def test_file_input(self):
        runner = make_starter(
            args=[Argument('input', "$(value)", symlink="input.in")]
        )
        yield self._check_args, runner, {'input': "my_file.txt"}, ["input.in"]
        yield self._check_args, runner, {'input': None}, []
        yield self._check_args, runner, {}, []

    def test_repeated_array_input(self):
        runner = make_starter(args=[Argument('array', "-m=$(value)")])
        yield (self._check_args, runner,
               {'array': ['a', 'b', 'c', 'd']},
               ['-m=a', '-m=b', '-m=c', '-m=d'])
        yield self._check_args, runner, {'array': []}, []

    def test_joined_array_input(self):
        runner = make_starter(args=[Argument('array', "-m=$(value)", join=",")])
        yield self._check_args, runner, {'array': ["a", "b", "c"]}, ["-m=a,b,c"]

    def test_space_joined_array(self):
        runner = make_starter(args=[Argument('array', "-m $(value)", join=" ")])
        yield (self._check_args, runner,
               {'array': ["a", "b", "c"]},
               ["-m", "a b c"])


class TestJobExecution:

    def setup(self):
        self.work_dir = tempfile.TemporaryDirectory()

    def teardown(self):
        self.work_dir.cleanup()

    def test_commands_started(self):
        starter = make_starter(
            base_command="example.bin",
            args=[Argument("option", "-o $(value)")]
        )
        starter.runner = MagicMock()
        cwd = os.path.join(self.work_dir.name, "job000")
        params = {"option": "val"}
        starter.start([(params, cwd)])
        starter.runner.start.assert_called_once_with(
            [Command(args=['example.bin', '-o', 'val'], cwd=cwd, env=starter.env)]
        )

    def test_work_dir_created(self):
        starter = make_starter()
        starter.runner = MagicMock()
        cwd = os.path.join(self.work_dir.name, "job000")
        starter.start([({}, cwd)])
        assert_true(os.path.isdir(cwd))

    def test_run_with_parameters(self):
        starter = make_starter(
            base_command="command.bin",
            args=[
                Argument("param1", "-p1 $(value)"),
                Argument("param2", "-p2 $(value)"),
                Argument("option1", "$(value)", default="foo"),
                Argument("option2", "-opt=$(value)", default="bar")
            ]
        )
        cwd = os.path.join(self.work_dir.name, "job000")
        params = {"param2": "xxx", "option2": "yyy"}
        starter.runner = MagicMock()
        starter.start([(params, cwd)])
        args, kwargs = starter.runner.start.call_args
        commands, = args
        assert_equal(len(commands), 1)
        cmd: Command = commands[0]
        assert_list_equal(cmd.args, ["command.bin", "-p2", "xxx", "foo", "-opt=yyy"])
        assert_equal(cmd.cwd, cwd)
        assert_equal(cmd.env, starter.env)

    def test_returned_job(self):
        starter = make_starter()
        starter.runner = MagicMock()
        job = Job('c0ffee', self.work_dir.name)
        starter.runner.start.return_value = [job]
        jobs = starter.start([({}, self.work_dir.name)])
        assert_list_equal(jobs, [job])

    def test_symlink_is_created(self):
        starter = make_starter(
            base_command="cat",
            args=[Argument("file", "$(value)", symlink="input.txt")]
        )
        infile = tempfile.NamedTemporaryFile()
        infile.write(b'hello world\n')
        infile.flush()
        starter.runner = MagicMock()
        starter.start([({"file": infile.name}, self.work_dir.name)])
        fp = os.path.join(self.work_dir.name, "input.txt")
        assert filecmp.cmp(infile.name, fp), "Files are not identical"
