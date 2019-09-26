import pytest

from slivka.server.forms.fields import TextField, ValidationError


@pytest.fixture('module')
def default_field():
    return TextField('name')


# to_python tests

def test_str_to_python(default_field):
    assert default_field.to_python('foo') == 'foo'


def test_empty_to_python(default_field):
    assert default_field.to_python('') is None


def test_none_to_python(default_field):
    assert default_field.to_python(None) is None


# empty value validation

def test_validate_none(default_field):
    with pytest.raises(ValidationError):
        default_field.validate(None)


def test_validate_none_required():
    field = TextField('name', required=True)
    with pytest.raises(ValidationError):
        field.validate(None)


def test_validate_none_not_required():
    field = TextField('name', required=False)
    assert field.validate(None) is None


# validation with default provided

def test_validate_none_with_default():
    field = TextField('name', default='bar')
    assert field.validate(None) == 'bar'


def test_validate_empty_with_default():
    field = TextField('name', default='bar')
    assert field.validate('') == 'bar'


def test_to_cmd_parameter(default_field):
    assert default_field.to_cmd_parameter('foobar') == 'foobar'
