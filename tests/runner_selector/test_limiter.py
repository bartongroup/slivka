from . import LimiterStub


def test_limiter_selection():
    limiter = LimiterStub()
    assert limiter({'use_foo': True}) == 'foo'


def test_limiter_rejection():
    limiter = LimiterStub()
    assert limiter({'no_choice': True}) is None


def test_limiter_priority():
    limiter = LimiterStub()
    assert limiter({
        "use_default": True,
        "use_foo": False,
        "use_bar": True
    }) == 'default'
