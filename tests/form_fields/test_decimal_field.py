from nose.tools import assert_raises, raises, assert_equal, assert_is_none

from slivka.server.forms.fields import DecimalField, ValidationError


# value conversion tests

def test_int_to_python():
    field = DecimalField("name")
    assert_equal(field.validate(10), 10.0)
    assert_equal(field.validate(-4), -4.0)
    assert_equal(field.validate(0), 0)


def test_float_to_python():
    field = DecimalField('name')
    assert_equal(field.validate(4.5), 4.5)


def test_number_str_to_python():
    field = DecimalField("name")
    assert_equal(field.validate('10'), 10.0)
    assert_equal(field.validate('0.01'), 0.01)


@raises(ValidationError)
def test_other_str_to_python():
    field = DecimalField("name")
    field.validate('xyzzy')


def test_none_to_python():
    field = DecimalField('name', required=False)
    assert field.validate(None) is None
    assert field.validate('') is None


@raises(ValidationError)
def test_false_to_python():
    field = DecimalField("name")
    field.validate(False)


@raises(ValidationError)
def test_true_to_python():
    field = DecimalField("name")
    field.validate(False)


# min/max validation
class TestBoundedValue:
    def setup(self):
        self.field = DecimalField("name", min=2.1, max=4.9)
        self.field_ex = DecimalField(
            "name_ex", min=2.1, max=4.9,
            min_exclusive=True, max_exclusive=True
        )

    def test_within_bounds(self):
        self.field.validate(3.14)

    def test_equal_to_max(self):
        self.field.validate(4.9)

    @raises(ValidationError)
    def test_more_tham_max(self):
        self.field.validate(5.2)

    @raises(ValidationError)
    def test_equal_to_max_exclusive(self):
        self.field_ex.validate(4.9)

    @raises(ValidationError)
    def test_less_than_min(self):
        self.field.validate(1.3)

    def test_equal_to_min(self):
        self.field.validate(2.1)

    def test_equal_to_min_exclusive(self):
        self.field.validate(2.1)


# empty value validation

@raises(ValidationError)
def test_validate_none():
    field = DecimalField("name")
    field.validate(None)


@raises(ValidationError)
def test_validate_none_required():
    field = DecimalField('name', required=True)
    field.validate(None)


def test_validate_none_not_required():
    field = DecimalField('name', required=False)
    assert_is_none(field.validate(None))


# validation with default

def test_validate_none_with_default():
    field = DecimalField('name', default=5.0)
    assert_equal(field.validate(None), 5.0)
    field = DecimalField('name', default=0.0)
    assert_equal(field.validate(None), 0.0)


def test_validate_empty_with_default():
    field = DecimalField('name', default=4.0)
    assert_equal(field.validate(''), 4.0)
    assert_equal(field.validate(()), 4.0)
    assert_equal(field.validate([]), 4.0)


def test_validate_value_with_default():
    field = DecimalField('name', default=4.0, max=5.0)
    assert_equal(field.validate(0), 0.0)
    assert_equal(field.validate(3.14), 3.14)
    with assert_raises(ValidationError):
        field.validate(5.1)

