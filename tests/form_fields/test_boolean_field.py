from functools import partial

from nose import SkipTest
from nose.tools import assert_is, raises, assert_true

from slivka.server.forms.fields import BooleanField, ValidationError


def test_bool_conversion():
    field = BooleanField('name', required=False)
    assert_is(field.run_validation(True), True)
    assert_is(field.run_validation(False), None)


def test_int_conversion():
    field = BooleanField('name', required=False)
    assert_is(field.run_validation(1), True)
    assert_is(field.run_validation(0), None)


def test_text_conversion():
    field = BooleanField('name', required=False)
    for text in ('false', 'FALSE', 'False', 'off', '0', 'no', 'NULL', 'NONE', ''):
        assert_is(field.run_validation(text), None)
    for text in ('true', 'TRUE', 'T', 'on', 'yes', 'Y'):
        assert_is(field.run_validation(text), True)
    assert_is(field.run_validation('foobar'), True)


def test_none_conversion():
    field = BooleanField('name', required=False)
    assert_is(field.run_validation(None), None)


# empty value validation

@raises(ValidationError)
def test_validate_none():
    field = BooleanField('name')
    field.validate(None)


@raises(ValidationError)
def test_validate_none_required():
    field = BooleanField('name', required=True)
    field.validate(None)


def test_validation_none_not_required():
    field = BooleanField('name', required=False)
    assert_is(field.validate(None), None)


# validation with default provided


class TestValidationWithDefault:
    def test_default_unset(self):
        field = BooleanField('name', required=False)
        check = partial(self.check_field, field)
        yield check, None, None
        yield check, False, None
        yield check, True, True
        yield check, (), None

    def test_default_none(self):
        field = BooleanField('name', required=False, default=None)
        check = partial(self.check_field, field)
        yield check, None, None
        yield check, False, None
        yield check, True, True

    def test_default_false(self):
        field = BooleanField('name', required=False, default=False)
        check = partial(self.check_field, field)
        yield check, None, None
        yield check, False, None
        yield check, True, True
        yield check, [], None

    def test_default_true(self):
        raise SkipTest("default value substitution no longer applies")
        field = BooleanField('name', required=False, default=True)
        check = partial(self.check_field, field)
        yield check, None, True
        yield check, False, None
        yield check, True, True
        yield check, {}, True
        yield check, '', True

    @staticmethod
    def check_field(field, value, expected):
        assert_is(field.validate(value), expected)


# command line parameter conversion

def test_true_to_cmd_parameter():
    field = BooleanField('name', required=False)
    assert_true(field.to_arg(True))


def test_none_to_cmd_parameter():
    field = BooleanField('name', required=False)
    assert_is(field.to_arg(None), None)


def test_false_to_cmd_parameter():
    field = BooleanField('name', required=False)
    assert_is(field.to_arg(False), None)
