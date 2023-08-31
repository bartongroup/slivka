from collections import defaultdict

import pytest
from unittest import mock

from sentinels import Sentinel

from slivka.utils.expression_parser import Expression, Token


@pytest.mark.parametrize(
    "expression, expected",
    [
        (
            "5 10 -3",
            [
                Token("NUMBER", 5, 0),
                Token("NUMBER", 10, 2),
                Token("NUMBER", -3, 5),
            ],
        ),
        ("3.5 0.001", [Token("NUMBER", 3.5, 0), Token("NUMBER", 0.001, 4)]),
        (
            "1.25E-4 2.01e2",
            [Token("NUMBER", 1.25e-4, 0), Token("NUMBER", 201.0, 8)],
        ),
        (
            '"hello" "1.05" "and"',
            [
                Token("STRING", "hello", 0),
                Token("STRING", "1.05", 8),
                Token("STRING", "and", 15),
            ],
        ),
        (
            "and or xor not null",
            [
                Token("OPERATOR", "and", 0),
                Token("OPERATOR", "or", 4),
                Token("OPERATOR", "xor", 7),
                Token("OPERATOR", "not", 11),
                Token("NULL", None, 15),
            ],
        ),
        (
            "foo_bar var with-dash",
            [
                Token("IDENTIFIER", "foo_bar", 0),
                Token("IDENTIFIER", "var", 8),
                Token("IDENTIFIER", "with-dash", 12),
            ],
        ),
        (
            "not-op me_and_you orion",
            [
                Token("IDENTIFIER", "not-op", 0),
                Token("IDENTIFIER", "me_and_you", 7),
                Token("IDENTIFIER", "orion", 18),
            ],
        ),
    ],
)
def test_tokenize_valid_tokens(expression, expected):
    assert list(Expression.tokenize(expression)) == expected


@pytest.mark.parametrize("expression", ["!invalid", "me@host", "me&you"])
def test_tokenize_invalid_tokens(expression):
    with pytest.raises(ValueError):
        list(Expression.tokenize(expression))


@pytest.mark.parametrize(
    "expression, symbol",
    [
        ("2 + 2", "+"),
        ("2 - 2", "-"),
        ("2 * 2", "*"),
        ("2 / 2", "/"),
        ("2 <= 2", "<="),
        ("2 >= 2", ">="),
        ("2 < 2", "<"),
        ("2 > 2", ">"),
        ("2 != 2", "!="),
        ("2 == 2", "=="),
    ],
)
def test_tokenize_binary_math_expression(expression, symbol):
    tokens = list(Expression.tokenize(expression))
    assert tokens[1].type == "OPERATOR"
    assert tokens[1].value == symbol


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("5", 5),
        ("2.45", 2.45),
        ("1.1e2", 110.0),
        ('"foobar"', "foobar"),
        ("null", None),
    ],
)
def test_eval_literals(expression, expected):
    assert Expression(expression).eval() == expected


def test_eval_identifier():
    assert (
        Expression("value").eval({"value": mock.sentinel.val})
        == mock.sentinel.val
    )


@pytest.fixture()
def context():
    return defaultdict(mock.MagicMock)


def test_eval_add(context):
    context["a"].__add__.return_value = mock.sentinel.retval
    assert Expression("a + b").eval(context) == mock.sentinel.retval
    context["a"].__add__.assert_called_with(context["b"])


def test_eval_sub(context):
    context["a"].__sub__.return_value = mock.sentinel.retval
    assert Expression("a - b").eval(context) == mock.sentinel.retval
    context["a"].__sub__.assert_called_with(context["b"])


def test_eval_mul(context):
    context["a"].__mul__.return_value = 8
    val = Expression("a * b").eval(context)
    assert val == 8
    context["a"].__mul__.assert_called_with(context["b"])


def test_eval_div(context):
    context["a"].__truediv__.return_value = mock.sentinel.retval
    val = Expression("a / b").eval(context)
    assert val == mock.sentinel.retval
    context["a"].__truediv__.assert_called_with(context["b"])


def test_eval_neg(context):
    context["a"].__neg__.return_value = mock.sentinel.retval
    val = Expression("-a").eval(context)
    assert val == mock.sentinel.retval
    context["a"].__neg__.assert_called_with()


def test_eval_le(context):
    context["a"].__le__.return_value = mock.sentinel.retval
    val = Expression("a <= b").eval(context)
    assert val == mock.sentinel.retval
    context["a"].__le__.assert_called_with(context["b"])


def test_eval_lt(context):
    context["a"].__lt__.return_value = mock.sentinel.retval
    val = Expression("a < b").eval(context)
    assert val == mock.sentinel.retval
    context["a"].__lt__.assert_called_with(context["b"])


def test_eval_ge(context):
    context["a"].__ge__.return_value = mock.sentinel.retval
    val = Expression("a >= b").eval(context)
    assert val == mock.sentinel.retval
    context["a"].__ge__.assert_called_with(context["b"])


def test_eval_gt(context):
    context["a"].__gt__.return_value = mock.sentinel.retval
    val = Expression("a > b").eval(context)
    assert val == mock.sentinel.retval
    context["a"].__gt__.assert_called_with(context["b"])


def test_eval_eq(context):
    context["a"].__eq__.return_value = mock.sentinel.retval
    val = Expression("a == b").eval(context)
    assert val == mock.sentinel.retval
    context["a"].__eq__.assert_called_with(context["b"])


def test_eval_ne(context):
    context["a"].__ne__.return_value = mock.sentinel.retval
    val = Expression("a != b").eval(context)
    assert val == mock.sentinel.retval
    context["a"].__ne__.assert_called_with(context["b"])


def test_eval_len(context):
    context["a"].__len__.return_value = 10
    val = Expression("#a").eval(context)
    assert val == 10
    context["a"].__len__.assert_called_with()


def test_eval_add_then_add(context):
    context["a"].__add__.return_value = context["c"]
    context["c"].__add__.return_value = mock.sentinel.retval
    val = Expression("a + b + d").eval(context)
    context["a"].__add__.assert_called_with(context["b"])
    context["c"].__add__.assert_called_with(context["d"])
    assert val == mock.sentinel.retval


def test_eval_mul_before_add(context):
    context["a"].__add__.return_value = mock.sentinel.retval
    context["b"].__mul__.return_value = mock.sentinel.prod
    val = Expression("a + b * c").eval(context)
    assert val == mock.sentinel.retval
    context["b"].__mul__.assert_called_with(context["c"])
    context["a"].__add__.assert_called_with(mock.sentinel.prod)


def test_eval_add_before_cmp(context):
    context["a"].__le__.return_value = mock.sentinel.retval
    context["b"].__add__.return_value = mock.sentinel.sum
    val = Expression("a <= b + c").eval(context)
    assert val == mock.sentinel.retval
    context["b"].__add__.assert_called_with(context["c"])
    context["a"].__le__.assert_called_with(mock.sentinel.sum)


def test_eval_paren_priority(context):
    context["c"].__eq__.return_value = mock.sentinel.x
    context["b"].__add__.return_value = mock.sentinel.y
    context["a"].__mul__.return_value = mock.sentinel.retval
    val = Expression("a * (b + (c == d))").eval(context)
    assert val == mock.sentinel.retval
    context["c"].__eq__.assert_called_with(context["d"])
    context["b"].__add__.assert_called_with(mock.sentinel.x)
    context["a"].__mul__.assert_called_with(mock.sentinel.y)
