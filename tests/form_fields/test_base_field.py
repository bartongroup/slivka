from nose.tools import assert_equal, raises, assert_is_none, assert_true, \
    assert_false, assert_list_equal, assert_raises
from werkzeug.datastructures import MultiDict

from slivka.server.forms.fields import BaseField, ValidationError, \
    ArrayFieldMixin


class FieldStub(BaseField):
    def run_validation(self, value):
        value = super().run_validation(value)
        if value == 'FAIL':
            raise ValidationError("Invalid value 'FAIL'", 'invalid')
        if value == 'CHANGEME':
            return 'CHANGED'
        return value


class ArrayFieldStub(ArrayFieldMixin, FieldStub):
    pass


class TestBasicProperties:
    def test_name(self):
        field = BaseField('foobar')
        assert_equal(field.name, 'foobar')

    def test_description(self):
        field = BaseField('name', description='example description')
        assert_equal(field.description, 'example description')

    def test_default_required(self):
        field = BaseField('name')
        assert_true(field.required)

    def test_required(self):
        field = BaseField('name', required=True)
        assert_true(field.required)

    def test_optional(self):
        field = BaseField('name', required=False)
        assert_false(field.required)

    def test_default(self):
        field = BaseField('name', default='default-value')
        assert_equal(field.default, 'default-value')
        assert_false(field.required)


class TestDataFetch:
    def setup(self):
        self.field = FieldStub('test')
        self.arr_field = ArrayFieldStub('test')

    def test_fetch_value(self):
        data = MultiDict({
            'alpha': 1,
            'bravo': -0.53,
            'test': 'field-value',
        })
        assert_equal(self.field.fetch_value(data, MultiDict()), 'field-value')

    def test_fetch_missing(self):
        data = MultiDict({
            'alpha': 1,
            'bravo': -0.53,
        })
        assert_is_none(self.field.fetch_value(data, MultiDict()))

    def test_fetch_array(self):
        data = MultiDict([('test', 'a'), ('test', 'b')])
        assert_list_equal(
            self.arr_field.fetch_value(data, MultiDict()), ['a', 'b'])

    def test_fetch_array_missing(self):
        assert_is_none(
            self.arr_field.fetch_value(MultiDict(), MultiDict()), [])


class TestValidation:
    def setup(self):
        self.field = FieldStub('name')
        self.opt_field = FieldStub('name', required=False)
        self.def_field = FieldStub('name', default=0, required=True)

    def test_valid_value(self):
        assert_equal(self.field.validate('value'), 'value')

    def test_value_changed(self):
        assert_equal(self.field.validate('CHANGEME'), 'CHANGED')

    @raises(ValidationError)
    def test_invalid_value(self):
        self.field.validate('FAIL')

    @raises(ValidationError)
    def test_missing_required_value(self):
        self.field.validate(None)

    def test_missing_optional_value(self):
        assert_is_none(self.opt_field.validate(None))
        assert_is_none(self.opt_field.validate(''))

    def test_required_with_default(self):
        assert_equal(self.def_field.validate(None), None)
        assert_equal(self.def_field.validate('value'), 'value')


class TestArrayValidation:
    def setup(self):
        self.field = ArrayFieldStub('name')
        self.opt_field = ArrayFieldStub('name', required=False)

    def test_valid_values(self):
        values = self.field.validate(['foo', 'bar'])
        assert_list_equal(values, ['foo', 'bar'])

    def test_no_values(self):
        with assert_raises(ValidationError) as ctx:
            self.field.validate([])
        assert_equal(ctx.exception.code, 'required')

    def test_list_of_nulls(self):
        with assert_raises(ValidationError) as ctx:
            self.field.validate([None, None])
        assert_equal(ctx.exception.code, 'required')

    def test_null_skipped(self):
        assert_list_equal(self.field.validate([None, 'alpha']), ['alpha'])

    def test_value_invalid(self):
        with assert_raises(ValidationError) as ctx:
            self.field.validate(['val', 'FAIL'])
        assert_equal(ctx.exception.code, 'invalid')

    def test_value_converted(self):
        values = self.field.validate(['CHANGEME', 'bravo'])
        assert_list_equal(values, ['CHANGED', 'bravo'])

    def test_opt_no_values(self):
        values = self.opt_field.validate([])
        assert_is_none(values)

    def test_opt_null(self):
        values = self.opt_field.validate(None)
        assert_is_none(values)


class TestCmdArg:
    def setup(self):
        self.field = FieldStub('test')
        self.array_field = ArrayFieldStub('test')

    def test_single_arg(self):
        yield self.check_cmd_arg, 1, '1'
        yield self.check_cmd_arg, 'foo', 'foo'
        yield self.check_cmd_arg, None, None
        yield self.check_cmd_arg, True, 'True'

    def test_arg_array(self):
        yield self.check_cmd_arg_array, [1, 2, 3], ['1', '2', '3']
        yield self.check_cmd_arg_array, ['1', 2], ['1', '2']
        yield (self.check_cmd_arg_array,
               ['alpha', None, 'bravo'], ['alpha', 'bravo'])
        yield self.check_null, [None, None]
        yield self.check_null, None

    def check_cmd_arg(self, value, expected):
        assert_equal(self.field.to_cmd_args(value), expected)

    def check_cmd_arg_array(self, value, expected):
        assert_list_equal(self.array_field.to_cmd_args(value), expected)

    def check_null(self, value):
        assert_is_none(self.array_field.to_cmd_args(value))
