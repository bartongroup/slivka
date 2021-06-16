from nose.tools import assert_list_equal, assert_is_none, assert_raises, \
    assert_equal
from werkzeug.datastructures import MultiDict

from slivka.server.forms.fields import IntegerArrayField, ValidationError


class TestArrayMixinFetch:
    def setup(self):
        self.field = IntegerArrayField('name')

    def test_fetch_value(self):
        val = self.field.fetch_value(MultiDict({'name': 0}), MultiDict())
        assert_list_equal(val, [0])

    def test_fetch_no_value(self):
        val = self.field.fetch_value(MultiDict(), MultiDict())
        assert_is_none(val)


class TestArrayMixinValidation:
    def setup(self):
        self.field = IntegerArrayField('name')
        self.opt_field = IntegerArrayField('name', required=False)

    def test_array(self):
        val = self.opt_field.validate([1, '2'])
        assert_list_equal(val, [1, 2])

    def test_null(self):
        val = self.opt_field.validate(None)
        assert_is_none(val)

    def test_empty_array(self):
        val = self.opt_field.validate([])
        assert_is_none(val)

    def test_opt_array_of_nulls(self):
        val = self.opt_field.validate([None, None])
        assert_is_none(val)

    def test_opt_array_containing_null(self):
        val = self.opt_field.validate([1, None, 3])
        assert_list_equal(val, [1, 3])

    def test_array_of_nulls(self):
        with assert_raises(ValidationError) as ctx:
            self.field.validate([None, None])
        assert_equal(ctx.exception.code, 'required')

    def test_array_containing_null(self):
        val = self.field.validate([1, None, 3])
        assert_equal(val, [1, 3])


class TestArrayMixinDefault:
    def test_valid(self):
        field = IntegerArrayField('name', default=[1, 2, 3])
        assert_list_equal(field.default, [1, 2, 3])

    def test_invalid_value(self):
        with assert_raises(RuntimeError):
            IntegerArrayField('name', default=[0, 1], min=1)

    def test_not_array(self):
        with assert_raises(RuntimeError):
            IntegerArrayField('name', default=1)

    def test_unset(self):
        field = IntegerArrayField('name')
        assert_is_none(field.default)
