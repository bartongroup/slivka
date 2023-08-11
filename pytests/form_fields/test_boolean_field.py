import pytest

from slivka.server.forms.fields import BooleanField


@pytest.mark.parametrize(
    "value, expected",
    [
        (True, True),
        (False, None),
        (None, None),
    ],
)
def test_bool_conversion(value, expected):
    field = BooleanField("test1", required=False)
    assert field.validate(value) is expected


@pytest.mark.parametrize(
    "value, expected", [(0, None), (1, True), (0.0, None), (1.0, True)]
)
def test_number_conversion(value, expected):
    field = BooleanField("test1", required=False)
    assert field.validate(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("false", None),
        ("FALSE", None),
        ("False", None),
        ("F", None),
        ("off", None),
        ("0", None),
        ("no", None),
        ("NO", None),
        ("N", None),
        ("NULL", None),
        ("null", None),
        ("NONE", None),
        ("", None),
        ("true", True),
        ("TRUE", True),
        ("True", True),
        ("T", True),
        ("on", True),
        ("1", True),
        ("yes", True),
        ("YES", True),
        ("Y", True),
    ],
)
def test_string_conversion(value, expected):
    field = BooleanField("test1", required=False)
    assert field.validate(value) is expected


@pytest.mark.parametrize(
    "value, expected", [(True, True), (False, None), (None, None)]
)
def test_to_cmd_parameter(value, expected):
    field = BooleanField("test1")
    assert field.to_arg(value) is expected
