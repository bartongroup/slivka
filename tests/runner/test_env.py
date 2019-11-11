import os

import pytest

from .stubs import runner_factory

os.environ['SLIVKA_HOME'] = '/tmp/slivkahome'


@pytest.fixture()
def runner():
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


def test_env_vars_present(runner):
    expected_vars = {'PATH', 'SLIVKA_HOME', 'EXAMPLE', 'BIN_PATH'}
    assert expected_vars.issubset(runner.env)


def test_predefined_slivka_home(runner):
    assert runner.env['SLIVKA_HOME'] == '/tmp/slivkahome'


def test_env_var_value(runner):
    assert runner.env['EXAMPLE'] == 'hello world'


def test_env_var_interpolation(runner):
    assert runner.env['BIN_PATH'] == '/tmp/slivkahome/bin'


def test_env_var_in_parameter(runner):
    assert runner.get_args({'param': 'xxx'}) == ['-foobar', 'xxx']


def test_env_var_injection(runner):
    assert runner.get_args({'param': '$EXAMPLE'}) == ['-foobar', '$EXAMPLE']
    assert runner.get_args({'param': '${EXAMPLE}'}) == ['-foobar', '${EXAMPLE}']


@pytest.fixture('function')
def set_global_env():
    os.environ['MYENV'] = 'example'
    yield
    del os.environ['MYENV']


@pytest.mark.usefixtures('set_global_env')
def test_global_env_in_base():
    runner = runner_factory(['/bin/${MYENV}'])
    assert runner.base_command == ['/bin/example']


def test_defined_env_in_base():
    runner = runner_factory(['${MYVAR}/bin'], env={'MYVAR': '/home'})
    assert runner.base_command == ['/home/bin']