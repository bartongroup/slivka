import os

from nose.tools import assert_equal, with_setup, assert_in, assert_list_equal

from .stubs import runner_factory

os.environ['SLIVKA_HOME'] = '/tmp/slivkahome'


def prepare_runner():
    return runner_factory(
        inputs={
            "param": {'arg': '-${MYVAR} $(value)'}
        },
        env={
            "EXAMPLE": "hello world",
            "BIN_PATH": "${SLIVKA_HOME}/bin",
            "MYVAR": "foobar"
        }
    )


def test_env_vars_present():
    runner = prepare_runner()
    assert_in('PATH', runner.env)
    assert_in('SLIVKA_HOME', runner.env)
    assert_in('EXAMPLE', runner.env)
    assert_in('BIN_PATH', runner.env)


def test_predefined_slivka_home():
    runner = prepare_runner()
    assert_equal(runner.env['SLIVKA_HOME'], '/tmp/slivkahome')


def test_env_var_value():
    runner = prepare_runner()
    assert_equal(runner.env['EXAMPLE'], 'hello world')


def test_env_var_interpolation():
    runner = prepare_runner()
    assert_equal(runner.env['BIN_PATH'], '/tmp/slivkahome/bin')


def test_env_var_in_parameter():
    runner = prepare_runner()
    assert_list_equal(runner.get_args({'param': 'xxx'}), ['-foobar', 'xxx'])


def test_env_var_injection():
    runner = prepare_runner()
    assert_list_equal(
        runner.get_args({'param': '$EXAMPLE'}),
        ['-foobar', '$EXAMPLE']
    )
    assert_list_equal(
        runner.get_args({'param': '${EXAMPLE}'}),
        ['-foobar', '${EXAMPLE}']
    )


def setup_myenv():
    os.environ['MYENV'] = 'example'


def teardown_myenv():
    del os.environ['MYENV']


@with_setup(setup_myenv, teardown_myenv)
def test_global_env_in_base():
    runner = runner_factory(['/bin/${MYENV}'])
    assert_list_equal(runner.base_command, ['/bin/example'])


def test_defined_env_in_base():
    runner = runner_factory(['${MYVAR}/bin'], env={'MYVAR': '/home'})
    assert_list_equal(runner.base_command, ['/home/bin'])
