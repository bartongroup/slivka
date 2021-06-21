from . import BaseSelectorStub


def test_limiter_selection():
    limiter = BaseSelectorStub()
    assert limiter({'use_foo': True}) == 'foo'


def test_limiter_rejection():
    limiter = BaseSelectorStub()
    assert limiter({'no_choice': True}) is None


def test_limiter_priority():
    limiter = BaseSelectorStub()
    assert limiter({
        "use_default": True,
        "use_foo": False,
        "use_bar": True
    }) == 'default'
