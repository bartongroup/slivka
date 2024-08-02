import pytest

from slivka.utils.env import expandvars


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"FOO": "0"},
        {"VARIABLE": "VALUE"},
    ],
)
@pytest.mark.parametrize(
    "string",
    [
        "",
        "VARIABLE",
        "no variable here",
    ],
)
def test_expandvars_no_variable(string, environ):
    assert expandvars(string, environ) == string


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"FOO": "0"},
        {"VAR": "VAL"},
    ],
)
@pytest.mark.parametrize(
    "string, expected",
    [
        ("$", "$"),
        ("$$", "$"),
        ("$$$$", "$$"),
        ("$$VAR", "$VAR"),
        ("$${VAR}", "${VAR}"),
    ],
)
def test_expandvars_escaped_dollar(string, environ, expected):
    assert expandvars(string, environ) == expected


@pytest.mark.parametrize(
    "environ",
    [
        {
            "VAR": "VALUE",
            "var": "value_lower",
            "FOO0": "FOO1",
            "FOO1": "FOO2",
            "HOME": "/home/slivka",
            "_VAR": "under_value",
        }
    ],
)
@pytest.mark.parametrize(
    "string, expected",
    [
        ("$VAR", "VALUE"),
        ("$var", "value_lower"),
        ("${VAR}", "VALUE"),
        ("$NONE", ""),
        ("${$VAR}", "${VALUE}"),
        ("${FOO0}", "FOO1"),
        ("My $VAR", "My VALUE"),
        ("$VAR-1", "VALUE-1"),
        ("$HOME/Documents", "/home/slivka/Documents"),
        ("$_VAR", "under_value"),
    ],
)
def test_expandvars_valid_variable(string, environ, expected):
    assert expandvars(string, environ) == expected


@pytest.mark.parametrize(
    "string, expected",
    [
        ("${VAR-NAME}", "${VAR-NAME}"),
        ("$0123", "$0123"),
        ("${VAR+}", "${VAR+}"),
        ("$%", "$%"),
        ("${{}}", "${{}}"),
    ],
)
def test_expandvars_illegal_identifier(string, expected):
    assert expandvars(string, {}) == expected
