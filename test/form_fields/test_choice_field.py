import math

import pytest

from slivka.server.forms.fields import (
    ChoiceField,
    ValidationError,
    ChoiceArrayField,
)

CHOICES = [("foo", "FOO"), ("bar", "BAR"), ("baz", "BAZ"), ("nothing", None)]


@pytest.fixture()
def choice_field():
    return ChoiceField("test1", choices=CHOICES)


@pytest.fixture()
def array_choice_field():
    return ChoiceArrayField("test1", choices=CHOICES)


@pytest.mark.parametrize("value", ["foo", "bar", "baz"])
def test_validate_if_value_is_choice_key(value, choice_field):
    assert choice_field.validate(value) == value


@pytest.mark.parametrize("value", ["FOO", "BAR", "BAZ"])
def test_validate_if_value_is_choice_value(value, choice_field):
    with pytest.raises(ValidationError):
        choice_field.validate(value)


@pytest.mark.parametrize("value", [1, "22/7", 42])
def test_validate_numeric_choices(value):
    field = ChoiceField(
        "test1",
        choices=[(1, -5), ("22/7", math.pi), (42, "meaning of the universe")],
    )
    assert field.validate(value) == value


def test_validate_invalid_value():
    field = ChoiceField("test1", choices=[("foo", 0)])
    with pytest.raises(ValidationError) as exc_info:
        field.validate("bar")
    assert exc_info.value.code == "invalid"


def test_validate_none_if_field_optional():
    field = ChoiceField("test1", choices=[("foo", 0)], required=False)
    assert field.validate(None) is None


@pytest.mark.parametrize("value", [None, "empty"])
def test_validate_none_if_none_is_a_choice(value):
    field = ChoiceField(
        "test1", choices=[(None, "none"), ("empty", None)], required=False
    )
    assert field.validate(value) == value


@pytest.mark.parametrize(
    "value, expected",
    [
        ("foo", "FOO"),
        ("bar", "BAR"),
        ("baz", "BAZ"),
        ("FOO", "FOO"),
        ("BAR", "BAR"),
        ("BAZ", "BAZ"),
        ("nothing", None),
        (None, None),
        ("", ""),
        ("undefined", "undefined"),
    ],
)
def test_to_cmd_args(value, expected, choice_field):
    assert choice_field.to_arg(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (["foo", "bar"], ["FOO", "BAR"]),
        (["baz", "BAR", "foo"], ["BAZ", "BAR", "FOO"]),
        (["foo", None], ["FOO"]),
        (["bar", "nothing"], ["BAR"]),
        (None, None),
        ([], None),
        (["nothing"], None),
        (["undefined"], ["undefined"]),
    ],
)
def test_array_to_cmd_args(value, expected, array_choice_field):
    assert array_choice_field.to_arg(value) == expected
