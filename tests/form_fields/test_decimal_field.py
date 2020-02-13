import pytest

from slivka.server.forms.fields import DecimalField, ValidationError


@pytest.fixture('module')
def default_field():
    return DecimalField('name')


# value conversion tests

def test_int_to_python(default_field):
    assert default_field.validate(10) == 10.0
    assert default_field.validate(-4) == -4.0
    assert default_field.validate(0) == 0


def test_float_to_python(default_field):
    assert default_field.validate(4.5) == 4.5


def test_number_str_to_python(default_field):
    assert default_field.validate('10') == 10.0
    assert default_field.validate('0.01') == 0.01


def test_other_str_to_python(default_field):
    with pytest.raises(ValidationError):
        default_field.validate('xyzzy')


def test_none_to_python():
    field = DecimalField('name', required=False)
    assert field.validate(None) is None
    assert field.validate('') is None


def test_bool_to_python(default_field):
    with pytest.raises(ValidationError):
        default_field.validate(False)
    with pytest.raises(ValidationError):
        default_field.validate(True)


# min/max validation

def test_validate_max_bound():
    field = DecimalField('name', max=4.9)
    with pytest.raises(ValidationError):
        field.validate(5.0)
    assert field.validate(4.9) == 4.9
    assert field.validate(-10) == -10.0


def test_validate_max_exclusive():
    field = DecimalField('name', max=4.9, max_exclusive=True)
    with pytest.raises(ValidationError):
        field.validate(4.9)
    assert field.validate(4.2) == 4.2


def test_validate_min_bound():
    field = DecimalField('name', min=2.1)
    with pytest.raises(ValidationError):
        field.validate(1.3)
    assert field.validate(2.1) == 2.1
    assert field.validate(2.3) == 2.3


def test_validate_min_exclusive():
    field = DecimalField('name', min=2.1, min_exclusive=True)
    with pytest.raises(ValidationError):
        field.validate(2.1)
    assert field.validate(2.2) == 2.2


# empty value validation

def test_validate_none(default_field):
    with pytest.raises(ValidationError):
        default_field.validate(None)


def test_validate_none_required():
    field = DecimalField('name', required=True)
    with pytest.raises(ValidationError):
        field.validate(None)


def test_validate_none_not_required():
    field = DecimalField('name', required=False)
    assert field.validate(None) is None


# validation with default

def test_validate_none_with_default():
    field = DecimalField('name', default=5.0)
    assert field.validate(None) == 5.0
    field = DecimalField('name', default=0.0)
    assert field.validate(None) == 0.0


def test_validate_empty_with_default():
    field = DecimalField('name', default=4.0)
    assert field.validate('') == 4.0
    assert field.validate(()) == 4.0
    assert field.validate([]) == 4.0


def test_validate_value_with_default():
    field = DecimalField('name', default=4.0, max=5.0)
    assert field.validate(0) == 0.0
    assert field.validate(3.14) == 3.14
    with pytest.raises(ValidationError):
        field.validate(5.1)

