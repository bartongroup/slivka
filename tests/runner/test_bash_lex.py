from nose.tools import assert_equal

from slivka.scheduler.runners._bash_lex import bash_quote


def test_quote_empty():
    assert_equal(bash_quote(""), "''")


def test_quote_letters():
    assert_equal(bash_quote("parameter"), "parameter")


def test_quote_numbers():
    assert_equal(bash_quote("01234abc"), "01234abc")


def test_quote_space():
    assert_equal(bash_quote("some parameter"), "'some parameter'")


def test_quote_safe_special():
    """Test special chars that don't need to be quoted"""
    for c in ',._+:@%/-':
        prm = 'some' + c + 'param'
        yield assert_equal, bash_quote(prm), prm


def test_quote_unsafe_special():
    """Test special chars that should be surrounded by quotes"""
    for c in '!#$&()[];<>\\"':
        prm = 'some' + c + 'param'
        yield assert_equal, bash_quote(prm), "'" + prm + "'"


def test_quote_quote():
    """Test if single quote is properly quoted"""
    assert_equal(bash_quote("some'param"), "$'some\\'param'")


def test_quote_basic_control():
    """Test if control characters are quoted and escaped"""
    yield assert_equal, bash_quote("some\r\nparam"), "$'some\\r\\nparam'"
    yield assert_equal, bash_quote("some\0param"), "$'some\\0param'"
    yield assert_equal, bash_quote("some\tparam"), "$'some\\tparam'"
    yield assert_equal, bash_quote("some\x1bparam"), "$'some\\eparam'"
    yield assert_equal, bash_quote("some\x08param"), "$'some\\bparam'"


def test_quote_backslash_escape():
    """Test if backslash is escaped in ANSI-C quote"""
    assert_equal(bash_quote("some\\param\n"), "$'some\\\\param\\n'")


def test_quote_advanced_control():
    """Test if advanced control chars are quoted and escaped using hex codes"""
    yield assert_equal, bash_quote("\x01"), "$'\\x01'"
    yield assert_equal, bash_quote("\x02"), "$'\\x02'"
    yield assert_equal, bash_quote("\x03"), "$'\\x03'"
    yield assert_equal, bash_quote("\x0f"), "$'\\x0F'"
    yield assert_equal, bash_quote("\x10"), "$'\\x10'"
