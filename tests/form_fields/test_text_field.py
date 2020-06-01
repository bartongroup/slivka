from nose.tools import assert_equal, raises, assert_is

from slivka.server.forms.fields import TextField, ValidationError


# valid value validation

def test_valid_string():
    field = TextField("name")
    assert_equal(field.validate('foo'), 'foo')


# empty value validation

@raises(ValidationError)
def test_validate_none():
    field = TextField("name")
    field.validate(None)


@raises(ValidationError)
def test_validate_none_required():
    field = TextField('name', required=True)
    field.validate(None)


@raises(ValidationError)
def test_validate_empty_required():
    field = TextField('name', required=True)
    field.validate('')


def test_validate_empty_not_required():
    field = TextField('name', required=False)
    assert_is(field.validate(''), None)


def test_validate_none_not_required():
    field = TextField('name', required=False)
    assert_is(field.validate(None), None)


# validation with default provided

def test_validate_none_with_default():
    field = TextField('name', default='bar')
    assert_equal(field.validate(None), 'bar')


def test_validate_empty_with_default():
    field = TextField('name', default='bar')
    assert_equal(field.validate(''), 'bar')


def test_to_cmd_parameter():
    field = TextField("name")
    assert_equal(field.to_cmd_parameter('foobar'), 'foobar')
