import pytest

from slivka.server.forms.fields import (
    IntegerField,
    ValidationError,
    IntegerArrayField,
)


def test_invalid_bounds_raises_exception():
    with pytest.raises(ValueError):
        IntegerField(10, 5)


@pytest.mark.parametrize(
    "value, expected",
    [
        (10, 10),
        (-8, -8),
        (0, 0),
        (1, 1),
        ("15", 15),
        ("-4", -4),
    ],
)
def test_convert_valid_integers(value, expected):
    field = IntegerField("test1")
    assert field.validate(value) == expected


@pytest.mark.parametrize(
    "values, expected",
    [
        ([1, 2, 4, 8], [1, 2, 4, 8]),
        (["1", 4, "16"], [1, 4, 16]),
        ([1, None, -1], [1, -1]),
    ],
)
def test_array_convert_valid_integers(values, expected):
    field = IntegerArrayField("test1")
    assert field.validate(values) == expected


@pytest.mark.parametrize("value", [(None,), ("",)])
def test_empty_values(value):
    field = IntegerField("test1", required=False)
    assert field.validate(value) is None


@pytest.mark.parametrize("value", [3.1415, "0.65", "xyz", True, False, "0xFF"])
def test_illegal_value(value):
    field = IntegerField("test1", required=False)
    with pytest.raises(ValidationError):
        field.validate(value)


@pytest.mark.parametrize(
    "bounds, value, err_code",
    [
        ((0, 1), -1, "min_value"),
        ((0, 1), -999999, "min_value"),
        ((0, 1), 2, "max_value"),
        ((0, 1), 99999, "max_value"),
        ((-40, -20), -19, "max_value"),
        ((-40, -20), -41, "min_value"),
        ((40, 80), 81, "max_value"),
        ((40, 80), 39, "min_value"),
        ((20, None), 19, "min_value"),
        ((20, None), 0, "min_value"),
        ((None, -10), 10, "max_value"),
        ((None, -10), 0, "max_value"),
    ],
)
def test_validate_if_value_not_in_bounds(bounds, value, err_code):
    kw = {}
    if bounds[0] is not None:
        kw["min"] = bounds[0]
    if bounds[1] is not None:
        kw["max"] = bounds[1]
    field = IntegerField("test1", **kw)
    with pytest.raises(ValidationError) as exc_info:
        field.validate(value)
    assert exc_info.value.code == err_code


@pytest.mark.parametrize(
    "bounds, value",
    [
        ((0, 1), 0),
        ((0, 1), 1),
        ((-40, 20), 0),
        ((-40, 20), -40),
        ((-40, 20), 20),
        ((-40, 20), 8),
        ((None, 0), -999999),
        ((0, None), 999999),
        ((None, None), 0),
        ((None, None), -999999),
        ((None, None), 999999),
        ((0, 1), None),
    ],
)
def test_validate_if_value_in_bounds(bounds, value):
    kw = {}
    if bounds[0] is not None:
        kw["min"] = bounds[0]
    if bounds[1] is not None:
        kw["max"] = bounds[1]
    field = IntegerField("test1", required=False, **kw)
    assert field.validate(value) == value
