import os

import pytest

from .stubs import RunnerStub, runner_factory

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
