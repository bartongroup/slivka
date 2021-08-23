import os

from nose.tools import (
    assert_equal, assert_sequence_equal, assert_in,
    assert_list_equal
)

from slivka.conf import ServiceConfig
from .stub import RunnerStub

Argument = ServiceConfig.Argument


def setup_module():
    os.environ['SLIVKA_HOME'] = '/tmp/slivkahome'
    os.environ['GLOBAL'] = 'global'


def teardown_module():
    del os.environ['SLIVKA_HOME']


class EnvTest:
    def setup(self):
        self.runner = RunnerStub(
            None,
            command="/bin/${MY_VAR}",
            args=[
                Argument('param', "--${MY_VAR}"),
                Argument('value', "$(value)")
            ],
            outputs=[],
            env={
                "EXAMPLE": "example",
                "BIN_PATH": "${SLIVKA_HOME}/bin",
                "MY_VAR": "foobar"
            }
        )

    def test_vars_present(self):
        for var in ['PATH', 'SLIVKA_HOME', 'EXAMPLE', 'BIN_PATH', 'MY_VAR']:
            yield self._check_in_env, var

    def _check_in_env(self, item):
        assert_in(item, self.runner.env)

    def test_slivka_home(self):
        assert_equal(self.runner.env['SLIVKA_HOME'], '/tmp/slivkahome')

    def test_env_interpolation(self):
        assert_equal(self.runner.env['BIN_PATH'], '/tmp/slivkahome/bin')

    def test_arg_interpolation(self):
        assert_sequence_equal(
            self.runner.build_args({'param': '1'}), ['--foobar']
        )

    @staticmethod
    def test_command_interpolation_global():
        runner = RunnerStub(command="/bin/${GLOBAL}")
        assert_sequence_equal(runner.command, ["/bin/global"])

    def test_command_interpolation_defined(self):
        assert_sequence_equal(self.runner.command, ["/bin/foobar"])

    def test_env_var_injection(self):
        assert_sequence_equal(
            self.runner.build_args({'value': '$EXAMPLE'}), ["$EXAMPLE"]
        )
        assert_sequence_equal(
            self.runner.build_args({'value': "${EXAMPLE}"}), ["${EXAMPLE}"]
        )


class TestBuildArgs:
    @staticmethod
    def _check_args(runner, inputs, args):
        assert_list_equal(runner.build_args(inputs), args)

    def test_symbol_delimited_option(self):
        runner = RunnerStub(
            args=[Argument('myoption', '--option=$(value)')],
        )
        yield self._check_args, runner, {}, []
        yield self._check_args, runner, {'myoption': None}, []
        yield self._check_args, runner, {'myoption': ''}, ['--option=']
        yield self._check_args, runner, {'myoption': 'my value'}, ["--option=my value"]

    def test_space_delimited_option(self):
        runner = RunnerStub(
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
        runner = RunnerStub(
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
        runner = RunnerStub(
            args=[Argument('myflag', "--flag")]
        )
        yield self._check_args, runner, {}, []
        yield self._check_args, runner, {'myflag': False}, []
        yield self._check_args, runner, {'myflag': None}, []
        yield self._check_args, runner, {'myflag': "true"}, ["--flag"]

    def test_default_substitution(self):
        runner = RunnerStub(
            args=[Argument('input', "-v=$(value)", default="default")]
        )
        yield self._check_args, runner, {'input': 'foo'}, ['-v=foo']
        yield self._check_args, runner, {'input': None}, ['-v=default']
        yield self._check_args, runner, {'input': ''}, ['-v=']
        yield self._check_args, runner, {}, ["-v=default"]

    def test_parameters_ordering(self):
        runner = RunnerStub(
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
            {'iters': "5", 'outfile': 'output.txt', 'verbose': "true", 'infile': 'input.txt'},
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
        runner = RunnerStub(
            args=[Argument('input', "$(value)", symlink="input.in")]
        )
        yield self._check_args, runner, {'input': "my_file.txt"}, ["input.in"]
        yield self._check_args, runner, {'input': None}, []
        yield self._check_args, runner, {}, []

    def test_repeated_array_input(self):
        runner = RunnerStub(args=[Argument('array', "-m=$(value)")])
        yield (self._check_args, runner,
               {'array': ['a', 'b', 'c', 'd']},
               ['-m=a', '-m=b', '-m=c', '-m=d'])
        yield self._check_args, runner, {'array': []}, []

    def test_joined_array_input(self):
        runner = RunnerStub(args=[Argument('array', "-m=$(value)", join=",")])
        yield self._check_args, runner, {'array': ["a", "b", "c"]}, ["-m=a,b,c"]

    def test_space_joined_array(self):
        runner = RunnerStub(args=[Argument('array', "-m $(value)", join=" ")])
        yield (self._check_args, runner,
               {'array': ["a", "b", "c"]},
               ["-m", "a b c"])
