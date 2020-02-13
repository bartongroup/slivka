import pytest
from werkzeug.datastructures import MultiDict

from slivka.server.forms.fields import BaseField, ValidationError


class BaseFieldStub(BaseField):
    def run_validation(self, value):
        value = super().run_validation(value)
        if value == 'FAIL':
            raise ValidationError("MESSAGE", 'code')
        return value


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


def test_validate_valid_value():
    field = BaseFieldStub('name')
    assert field.validate('value') == 'value'


def test_validate_invalid_value():
    field = BaseFieldStub('name')
    with pytest.raises(ValidationError):
        field.validate('FAIL')


def test_validate_missing_required_value():
    field = BaseFieldStub('name')
    with pytest.raises(ValidationError):
        field.validate(None)


def test_validate_missing_not_required_value():
    field = BaseFieldStub('name', required=False)
    assert field.validate(None) is None
    assert field.validate('') is None


def test_validate_with_default_value():
    field = BaseFieldStub('name', default='value')
    assert field.validate(None) == 'value'
    assert field.validate('other value') == 'other value'


def test_int_to_cmd_parameter(example_field: BaseField):
    assert example_field.to_cmd_parameter(1) == 1


def test_str_to_cmd_parameter(example_field: BaseField):
    assert example_field.to_cmd_parameter('foo') == 'foo'


def test_none_to_cmd_parameter(example_field: BaseField):
    assert example_field.to_cmd_parameter(None) is None


def test_true_to_cmd_parameter(example_field: BaseField):
    assert bool(example_field.to_cmd_parameter(True)) is True


def test_false_to_cmd_parameter(example_field: BaseField):
    assert bool(example_field.to_cmd_parameter(False)) is False


def test_get_multiple_value_from_data():
    field = BaseField('name', multiple=True)
    data = MultiDict([('name', 'a'), ('name', 'b')])
    assert field.value_from_request_data(data, MultiDict()) == ['a', 'b']


def test_multiple_missing_value_from_data():
    field = BaseField('name', multiple=True)
    assert field.value_from_request_data(MultiDict(), MultiDict()) == []


def test_validate_multiple_valid_values():
    field = BaseFieldStub('name', multiple=True)
    assert field.validate(['foo', 'bar']) == ['foo', 'bar']


def test_validate_multiple_no_values():
    field = BaseFieldStub('name', multiple=True)
    with pytest.raises(ValidationError):
        field.validate([])


def test_validate_multiple_with_default():
    field = BaseFieldStub('name', multiple=True, default='default')
    assert field.validate(None) == ['default']
    assert field.validate([]) == ['default']


def test_validate_multiple_containing_invalid():
    field = BaseFieldStub('name', multiple=True)
    with pytest.raises(ValidationError):
        field.validate(['x', 'y', 'FAIL', 'z'])