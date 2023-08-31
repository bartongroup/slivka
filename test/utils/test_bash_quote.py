import pytest


from slivka.scheduler.runners._bash_lex import bash_quote


@pytest.mark.parametrize(
    "token",
    [
        "parameter",
        "01234",
        "name3",
        "1value",
        "--line-length",
        "user@host.com",
        "key.value",
        "hello+world",
        "hello_world",
        "iana:text/plain",
        "1,2,3",
        "http://example.org",
        ",",
        ".",
        "_",
        "+",
        ":",
        "@",
        "%",
        "/",
        "-",
    ],
)
def test_quote_safe_characters_not_quoted(token):
    assert bash_quote(token) == token


def test_quote_empty_string():
    assert bash_quote("") == "''"


@pytest.mark.parametrize(
    "token",
    [
        "!",
        "#",
        "$",
        "&",
        "*",
        "(",
        ")",
        "[",
        "]",
        ";",
        "<",
        ">",
        "\\",
        '"',
        "!value",
        "#1",
        "http://example.org?key=val",
        "2 > 3",
        "(text)",
        "<text>",
        "\\n",
    ],
)
def test_quote_unsafe_characters_single_quoted(token):
    assert bash_quote(token) == f"'{token}'"


@pytest.mark.parametrize(
    "token, expected",
    [("'", "\\'"), ("'text'", "\\'text\\'"), ("o'sole", "o\\'sole")],
)
def test_quote_single_quote_dollar_quoted(token, expected):
    assert bash_quote(token) == f"$'{expected}'"


@pytest.mark.parametrize(
    "token, expected",
    [
        ("\r\n", "\\r\\n"),
        ("\0", "\\0"),
        ("\t", "\\t"),
        ("\x1B", "\\e"),
        ("\x08", "\\b"),
        ("\x01", "\\x01"),
        ("\x02", "\\x02"),
        ("\x03", "\\x03"),
        ("\x04", "\\x04"),
        ("\x0f", "\\x0F"),
        ("\x10", "\\x10"),
        ("\x1C", "\\x1C"),
    ],
)
def test_quote_control_characters_dollar_quoted(token, expected):
    assert bash_quote(token) == f"$'{expected}'"
