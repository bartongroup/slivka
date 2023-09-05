import pytest
from sentinels import Sentinel
from werkzeug.datastructures import MultiDict

from slivka.server.forms.fields import (
    BaseField,
    ArrayFieldMixin,
    ValidationError,
)

raises_validation_error = pytest.mark.raises(exception=ValidationError)

BaseArrayField = type("BaseArrayField", (ArrayFieldMixin, BaseField), {})


class FailingField(BaseField):
    def run_validation(self, value):
        value = super().run_validation(value)
        if value == Sentinel("FAIL"):
            raise ValidationError("Invalid value", "invalid")
        return value


FailingArrayField = type("FailingArrayField", (ArrayFieldMixin, FailingField), {})


class ReplacingField(BaseField):
    def run_validation(self, value):
        value = super().run_validation(value)
        return "other-" + str(value)


def test_id():
    field = BaseField("test1")
    assert field.id == "test1"


def test_name():
    field = BaseField("test1", name="test_name")
    assert field.name == "test_name"


def test_empty_name():
    field = BaseField("test1")
    assert field.name == ""


def test_description():
    field = BaseField("test1", description="example description")
    assert field.description == "example description"


def test_empty_description():
    field = BaseField("test1")
    assert field.description == ""


def test_required():
    field = BaseField("test1", required=True)
    assert field.required is True


def test_optional():
    field = BaseField("test1", required=False)
    assert field.required is False


def test_empty_required():
    field = BaseField("test1")
    assert field.required is True


def test_default_value():
    field = BaseField("test1", default=42)
    assert field.default == 42


def test_null_default_value():
    field = BaseField("test1", default=None)
    assert field.default is None


def test_empty_default_value():
    field = BaseField("test1")
    assert field.default is None


@pytest.mark.parametrize(
    "values, expected",
    [
        (MultiDict({"test1": "value"}), "value"),
        (
            MultiDict(
                {
                    "test0": "not this",
                    "test1": "value",
                    "test2": "also not this",
                }
            ),
            "value",
        ),
        (MultiDict({"test1": ""}), ""),
        (MultiDict({"test1": 0}), 0),
        (MultiDict({"test1": False}), False),
        (MultiDict({}), None),
        (MultiDict({"test1": None}), None),
        (MultiDict({"test0": 0, "test2": 2, "test3": 3}), None),
        (MultiDict({"test1": [12, 14, 16, 18]}), 12),
    ],
)
def test_fetch_value(values, expected):
    field = BaseField("test1")
    assert field.fetch_value(values, MultiDict()) == expected


@pytest.mark.parametrize(
    "values, expected",
    [
        (MultiDict({"test1": "value"}), ["value"]),
        (
            MultiDict({"test0": [3, 4, 5], "test1": [1, 1, 2, 3], "test2": []}),
            [1, 1, 2, 3],
        ),
        (MultiDict({}), None),
        (MultiDict({"test1": []}), None),
        (MultiDict({"test1": ""}), [""]),
        (MultiDict({"test1": None}), None),
    ],
)
def test_fetch_array_value(values, expected):
    field = BaseArrayField("test1")
    assert field.fetch_value(values, MultiDict()) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, 0),
        (1, 1),
        ("string", "string"),
        (True, True),
        pytest.param(False, None, marks=raises_validation_error),
        pytest.param(None, None, marks=raises_validation_error),
        pytest.param("", None, marks=raises_validation_error),
        pytest.param(Sentinel("FAIL"), None, marks=raises_validation_error),
    ],
)
def test_basic_validation_if_required(value, expected):
    field = FailingField("test1", required=True)
    assert field.validate(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, 0),
        (1, 1),
        ("string", "string"),
        (True, True),
        (False, False),
        (None, None),
        pytest.param("", "", marks=pytest.mark.xfail(reason='Behaviour to be decided')),
        pytest.param(Sentinel("FAIL"), None, marks=raises_validation_error),
    ],
)
def test_basic_validation_if_optional(value, expected):
    field = FailingField("test1", required=False)
    assert field.validate(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, 0),
        (1, 1),
        ("string", "string"),
        (Sentinel("ANY"), Sentinel("ANY")),
        (None, None),
        (False, False),
        pytest.param("", "", marks=pytest.mark.xfail(reason='Behaviour to be decided')),
        pytest.param(Sentinel("FAIL"), None, marks=raises_validation_error),
    ],
)
def test_basic_validation_with_default(value, expected):
    field = FailingField("test1", default=Sentinel("DEFAULT"))
    assert field.validate(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ([0, 0, 0], [0, 0, 0]),
        ([1, 2, 3], [1, 2, 3]),
        ("abc", ["a", "b", "c"]),
        (["alpha", "bravo"], ["alpha", "bravo"]),
        ([1, None, 3], [1, 3]),
        ([None, None, "x"], ["x"]),
        pytest.param([None], None, marks=raises_validation_error),
        pytest.param([""], None, marks=raises_validation_error),
        pytest.param([], None, marks=raises_validation_error),
        pytest.param([None, None], None, marks=raises_validation_error),
        pytest.param(["", "alpha"], None, marks=raises_validation_error),
    ],
)
def test_array_validation_if_required(value, expected):
    field = BaseArrayField("test1", required=True)
    assert field.validate(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ([0, 0, 0], [0, 0, 0]),
        ([1, 2, 3], [1, 2, 3]),
        ("abc", ["a", "b", "c"]),
        (["alpha", "bravo"], ["alpha", "bravo"]),
        ([1, None, 3], [1, 3]),
        ([None, None, "x"], ["x"]),
        ([None], None),
        pytest.param([""], [""], marks=pytest.mark.xfail(reason="Uncertain expected value")),
        ([], None),
        ([None, None], None),
        pytest.param(["", "alpha"], ["", "alpha"], marks=pytest.mark.xfail(reason="Uncertain expected value")),
    ],
)
def test_array_validation_if_optional(value, expected):
    field = BaseArrayField("test1", required=False)
    assert field.validate(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (1, "1"),
        (0, "0"),
        (True, "True"),
        (False, "False"),
        ("string", "string"),
        ("", ""),
        (None, None),
    ],
)
def test_to_cmd_args(value, expected):
    field = BaseField("test1")
    assert field.to_arg(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ([0, 1, 2], ["0", "1", "2"]),
        (["1", 2], ["1", "2"]),
        (["alpha", "bravo"], ["alpha", "bravo"]),
        (["alpha", None], ["alpha"]),
        ([None], None),
        ([None, None], None),
        (None, None),
    ],
)
def test_array_to_cmd_args(value, expected):
    field = BaseArrayField("test1")
    assert field.to_arg(value) == expected
