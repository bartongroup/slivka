import pytest

from slivka.server.forms.fields import BaseField


@pytest.fixture()
def example_field():
    return BaseField('myfield')


def test_field_name():
    field = BaseField('foobar')
    assert field.name == 'foobar'


def test_field_description():
    field = BaseField('name', description='example description')
    assert field.description == 'example description'


def test_get_value_from_data(example_field):
    data = {
        'alpha': 1,
        'beta': -0.53,
        'myfield': 'myvalue',
        'gamma': 'foobar'
    }
    assert example_field.value_from_request_data(data, {}) == 'myvalue'


def test_get_missing_value_from_data(example_field):
    data = {
        'alpha': 1,
        'beta': -0.53,
        'gamma': 'foobar'
    }
    assert example_field.value_from_request_data(data, {}) is None


def test_int_to_cmd_parameter(example_field: BaseField):
    assert example_field.to_cmd_parameter(1) == '1'


def test_str_to_cmd_parameter(example_field: BaseField):
    assert example_field.to_cmd_parameter('foo') == 'foo'


def test_none_to_cmd_parameter(example_field: BaseField):
    assert example_field.to_cmd_parameter(None) is None


def test_true_to_cmd_parameter(example_field: BaseField):
    assert bool(example_field.to_cmd_parameter(True)) is True


def test_false_to_cmd_parameter(example_field: BaseField):
    assert bool(example_field.to_cmd_parameter(False)) is False
