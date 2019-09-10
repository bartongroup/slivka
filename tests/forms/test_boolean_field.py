import pytest

from slivka.server.forms.fields import BooleanField, ValidationError


@pytest.fixture('module')
def default_field():
    return BooleanField('name')


# to_python tests

def test_bool_to_python(default_field):
    assert default_field.to_python(True) is True
    assert default_field.to_python(False) is None


def test_int_to_python(default_field):
    assert default_field.to_python(1) is True
    assert default_field.to_python(0) is None


def test_text_to_python(default_field):
    for text in ('false', 'FALSE', 'False', 'off', '0', 'no', 'NULL', 'NONE', ''):
        assert default_field.to_python(text) is None
    for text in ('true', 'TRUE', 'T', 'on', 'yes', 'Y'):
        assert default_field.to_python(text) is True
    assert default_field.to_python('foobar') is True


def test_none_to_python(default_field):
    assert default_field.to_python(None) is None


# empty value validation

def test_validate_none(default_field):
    with pytest.raises(ValidationError):
        default_field.validate(None)


def test_validate_none_required():
    field = BooleanField('name', required=True)
    with pytest.raises(ValidationError):
        field.validate(None)


def test_validation_none_not_required():
    field = BooleanField('name', required=False)
    assert field.validate(None) is None


# validation with default provided

def test_validate_none_with_default():
    field = BooleanField('name', default=True)
    assert field.validate(None) is True
    field = BooleanField('name', default=False)
    assert field.validate(None) is None


def test_validate_empty_with_default():
    field = BooleanField('name', default=True)
    assert field.validate({}) is True
    assert field.validate('') is True


def test_to_cmd_parameter(default_field):
    assert default_field.to_cmd_parameter(False) is None
    assert default_field.to_cmd_parameter(True)
    assert default_field.to_cmd_parameter(None) is None
