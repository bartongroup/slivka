import pytest

from slivka.server.forms.fields import IntegerField, ValidationError


@pytest.fixture('module')
def default_field():
    return IntegerField('name')


# value conversion tests

def test_int_conversion(default_field):
    assert default_field.validate(10) == 10
    assert default_field.validate(-8) == -8


def test_float_conversion(default_field):
    with pytest.raises(ValidationError):
        default_field.validate(2.43)


def test_number_str_conversion(default_field):
    assert default_field.validate('15') == 15
    assert default_field.validate('-3') == -3


def test_decimal_str_conversion(default_field):
    with pytest.raises(ValidationError):
        default_field.validate('0.65')


def test_other_str_conversion(default_field):
    with pytest.raises(ValidationError):
        default_field.validate('xyz')


def test_none_to_conversion():
    field = IntegerField('name', required=False)
    assert field.validate(None) is None
    assert field.validate('') is None


def test_bool_conversion(default_field):
    with pytest.raises(ValidationError):
        default_field.validate(True)
    with pytest.raises(ValidationError):
        default_field.validate(False)


def test_zero_conversion(default_field):
    # checks if 0 is not accidentally converted to None or False
    assert default_field.validate(0) is 0


# min/max validation

def test_validate_more_than_max():
    field = IntegerField('name', max=7)
    with pytest.raises(ValidationError):
        field.validate(8)


def test_validate_equal_to_max():
    field = IntegerField('name', max=7)
    assert field.validate(7) == 7


def test_validate_less_than_max():
    field = IntegerField('name', max=7)
    assert field.validate(6) == 6


def test_validate_more_than_min():
    field = IntegerField('name', min=7)
    assert field.validate(8) == 8


def test_validate_equal_to_min():
    field = IntegerField('name', min=7)
    assert field.validate(7)


def test_validate_less_than_min():
    field = IntegerField('name', min=7)
    with pytest.raises(ValidationError):
        field.validate(6)


# empty value validation

def test_validate_none(default_field):
    with pytest.raises(ValidationError):
        default_field.validate(None)


def test_validate_none_required():
    field = IntegerField('name', required=True)
    with pytest.raises(ValidationError):
        field.validate(None)


def test_validate_none_not_required():
    field = IntegerField('name', required=False)
    assert field.validate(None) is None


# validation with default

def test_validate_none_with_default():
    field = IntegerField('name', default=5)
    assert field.validate(None) == 5
    field = IntegerField('name', default=0)
    assert field.validate(None) == 0


def test_validate_empty_with_default():
    field = IntegerField('name,', default=3)
    assert field.validate('') == 3
    assert field.validate(()) == 3


def test_validate_valid_value_with_default():
    field = IntegerField('name', default=4, max=8)
    assert field.validate(1) == 1
    assert field.validate(0) == 0


def test_validate_invalid_value_with_default():
    field = IntegerField('name', default=4, max=8)
    with pytest.raises(ValidationError):
        field.validate(10)


# multiple values validation

def test_multiple_valid_values():
    field = IntegerField('name', multiple=True)
    assert field.validate([1, 2, 4, 8]) == [1, 2, 4, 8]
    assert field.validate(['1', 4, '6']) == [1, 4, 6]


def test_multiple_invalid_value():
    field = IntegerField('name', multiple=True)
    with pytest.raises(ValidationError):
        field.validate([4, 5, 'a'])