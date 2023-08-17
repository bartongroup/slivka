import pytest

from slivka.server.forms.fields import TextField, ValidationError


@pytest.mark.parametrize("value", ["foo", "bar"])
def test_validate_valid_string(value):
    field = TextField("test1")
    assert field.validate(value) == value


@pytest.mark.parametrize("value", ["", None])
def test_validate_empty_value_raise_required_error(value):
    field = TextField("test1")
    with pytest.raises(ValidationError) as exc_info:
        field.validate(value)
    assert exc_info.value.code == "required"


@pytest.mark.parametrize("value", ["", None])
def test_validate_empty_value_if_optional_converted_to_none(value):
    field = TextField("test1", required=False)
    assert field.validate(value) is None


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("a", marks=pytest.mark.raises(exception=ValidationError)),
        pytest.param(
            "aaa", marks=pytest.mark.raises(exception=ValidationError)
        ),
        pytest.param("aaaaa"),
        pytest.param("abababa"),
        pytest.param("ababababa"),
    ],
)
def test_validate_min_length(value):
    field = TextField("test1", min_length=5)
    assert field.validate(value) == value


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("a"),
        pytest.param("aaa"),
        pytest.param("aaaaa"),
        pytest.param(
            "abababa", marks=pytest.mark.raises(exception=ValidationError)
        ),
        pytest.param(
            "ababababa", marks=pytest.mark.raises(exception=ValidationError)
        ),
    ],
)
def test_validate_max_length(value):
    field = TextField("test1", max_length=5)
    assert field.validate(value) == value


@pytest.mark.parametrize(
    "value, expected", [("foobar", "foobar"), ("", ""), (None, None)]
)
def test_to_cmd_arg(value, expected):
    field = TextField("test1")
    assert field.to_arg(value) == expected
