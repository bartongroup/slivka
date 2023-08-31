import math

import pytest

from slivka.server.forms.fields import DecimalField, ValidationError


@pytest.mark.parametrize(
    "value, expected",
    [
        (0.4, 0.4),
        (2.1e5, 210000.0),
        (0.0, 0.0),
        (5, 5.0),
        (1e-3, 0.001),
        ("0.125", 0.125),
        ("5", 5.0),
        ("-12.3", -12.3),
        ("3.1415e3", 3141.5),
        (".5", 0.5),
        ("inf", math.inf),
        ("-inf", -math.inf),
    ],
)
def test_convert_valid_value(value, expected):
    field = DecimalField("test1")
    assert field.validate(value) == expected


@pytest.mark.parametrize("value", [None, ""])
def test_convert_empty_value(value):
    field = DecimalField("test1", required=False)
    assert field.validate(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "xyz",
        "0xFF",
        "3.14.15",
        "- 5",
        object(),
        True,
        False,
    ],
)
def test_convert_invalid_value(value):
    field = DecimalField("test1")
    with pytest.raises(ValidationError) as exc_info:
        field.validate(value)
    assert exc_info.value.code == "invalid"


@pytest.mark.parametrize("value", [None, ""])
def test_convert_empty_value(value):
    field = DecimalField("test1", required=False)
    assert field.validate(value) is None


@pytest.mark.parametrize(
    "bounds, value",
    [
        ((0.0, 5.0), 0.0),
        ((0.0, 5.0), 3.5),
        ((0.0, 5.0), 5.0),
        ((-10.0, None), 0.0),
        ((10.0, None), 10.0),
        ((10.0, None), 99999.0),
        ((10.0, None), math.inf),
        ((None, 5.0), 0.0),
        ((None, 5.0), -99999.0),
        ((None, 5.0), 5.0),
        ((None, 5.0), -math.inf),
        ((None, None), 99999.0),
        ((None, None), math.inf),
        ((None, None), -math.inf),
    ],
)
def test_validate_if_value_in_inclusive_bounds(bounds, value):
    kw = {}
    if bounds[0] is not None:
        kw["min"] = bounds[0]
    if bounds[1] is not None:
        kw["max"] = bounds[1]
    field = DecimalField("test1", **kw)
    assert field.validate(value) == value


@pytest.mark.parametrize(
    "bounds, value",
    [
        ((0.1, 5.0), 4.99999999),
        ((0.1, 5.0), 0.10000001),
        ((-2.5, None), -2.4999999),
        ((-2.5, None), 999999.9999),
        ((-2.5, None), math.inf),
    ],
)
def test_validate_if_value_in_exclusive_bounds(bounds, value):
    kw = {"min_exclusive": True, "max_exclusive": True}
    if bounds[0] is not None:
        kw["min"] = bounds[0]
    if bounds[1] is not None:
        kw["max"] = bounds[1]
    field = DecimalField("test1", **kw)
    assert field.validate(value) == value


@pytest.mark.parametrize(
    "bounds, value, err_code",
    [
        ((0.0, 5.0), 0.0, "min"),
        ((0.0, 5.0), 5.0, "max"),
        ((0.0, 5.0), 5.0000001, "max"),
        ((0.0, 5.0), math.inf, "max"),
        ((0.0, 5.0), -0.000001, "min"),
        ((0.0, 5.0), -math.inf, "min"),
    ],
)
def test_validate_if_value_not_in_exclusive_bounds(bounds, value, err_code):
    kw = {"min_exclusive": True, "max_exclusive": True}
    if bounds[0] is not None:
        kw["min"] = bounds[0]
    if bounds[1] is not None:
        kw["max"] = bounds[1]
    field = DecimalField("test1", **kw)
    with pytest.raises(ValidationError) as exc_info:
        field.validate(value)
    assert exc_info.value.code == f"{err_code}_value"
