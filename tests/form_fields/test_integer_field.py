from nose.tools import raises, assert_equal, assert_is, assert_list_equal

from slivka.server.forms.fields import IntegerField, ValidationError, \
    IntegerArrayField


class TestValue:
    def setup(self):
        self.field = IntegerField("name")

    def test_int(self):
        assert_equal(self.field.validate(10), 10)
        assert_equal(self.field.validate(-8), -8)

    @raises(ValidationError)
    def test_float(self):
        self.field.validate(2.43)

    def test_int_str(self):
        assert_equal(self.field.validate('15'), 15)
        assert_equal(self.field.validate('-3'), -3)

    @raises(ValidationError)
    def test_decimal_str(self):
        self.field.validate('0.65')

    @raises(ValidationError)
    def test_invalid_str_conversion(self):
        self.field.validate('xyz')

    def test_none_optional(self):
        self.field.required = False
        assert_is(self.field.validate(None), None)

    @raises(ValidationError)
    def test_none_required(self):
        self.field.validate(None)

    def test_empty(self):
        self.field.required = False
        assert_is(self.field.validate(''), None)

    @raises(ValidationError)
    def test_true(self):
        self.field.validate(True)

    @raises(ValidationError)
    def test_false(self):
        self.field.validate(False)

    def test_zero(self):
        # checks if 0 is not accidentally converted to None or False
        assert_is(self.field.validate(0), 0)


class TestBoundedValue:
    def setup(self):
        self.field = IntegerField("name", min=3, max=7)

    @raises(ValidationError)
    def test_validate_more_than_max(self):
        self.field.validate(8)

    def test_validate_equal_to_max(self):
        self.field.validate(7)

    @raises(ValidationError)
    def test_validate_less_than_min(self):
        self.field.validate(1)

    def test_validate_equal_to_min(self):
        self.field.validate(3)

    def test_validate_within_bounds(self):
        self.field.validate(5)


# validation with default

class TestDefault:
    def setup(self):
        self.field = IntegerField("name", default=49, min=-1)

    def test_none(self):
        assert_equal(self.field.validate(None), 49)

    def test_zero_default(self):
        # make sure that default = 0 is not treated as undefined
        field = IntegerField('name', default=0)
        assert_equal(field.validate(None), 0)

    def test_empty(self):
        assert_equal(self.field.validate(''), 49)
        assert_equal(self.field.validate(()), 49)

    def test_valid(self):
        assert_equal(self.field.validate(1), 1)

    def test_valid_zero(self):
        # make sure that 0 is not treated as False
        assert_equal(self.field.validate(0), 0)

    @raises(ValidationError)
    def test_invalid(self):
        self.field.validate(-20)


# multiple values validation

def test_multiple_valid_values():
    field = IntegerArrayField('name')
    assert_list_equal(field.validate([1, 2, 4, 8]), [1, 2, 4, 8])
    assert_list_equal(field.validate(['1', 4, '6']), [1, 4, 6])


@raises(ValidationError)
def test_multiple_invalid_value():
    field = IntegerArrayField('name')
    field.validate([4, 5, 'a'])
