from unittest.mock import MagicMock, sentinel
import pytest

from slivka.server import PrefixMiddleware

pytestmark = [pytest.mark.xfail(reason="correct behavior not implemented")]

# tests involving empty prefix

dataset = [
    # (path_info, expect_path, expect_script_name)
    ("/", "", "/"),
    ("/slivka", "/slivka", ""),
    ("/slivka/", "/slivka/", ""),
    ("/api_1_10/jobs", "/api_1_10/jobs", ""),
    ("/slivka/api/query/", "/slivka/api/query/", ""),
    ("/slivka///api/job", "/slivka///api/job", ""),
    ("///slivka", "//slivka", "/"),
    ("///", "//", "/")
]


@pytest.mark.parametrize(
    ('path_info', 'expect_path', 'expect_script_name'),
    dataset
)
def test_no_prefix(path_info, expect_path, expect_script_name):
    app = MagicMock()
    middleware = PrefixMiddleware(app)
    environ = {
        "PATH_INFO": path_info,
        "SCRIPT_NAME": ""
    }
    middleware(environ, sentinel.start_response)
    app.assert_called_once_with(
        {
            "PATH_INFO": expect_path,
            "SCRIPT_NAME": expect_script_name
        },
        sentinel.start_response
    )


@pytest.mark.parametrize(
    ('path_info', 'expect_path', 'expect_script_name'),
    dataset
)
def test_slash_prefix(path_info, expect_path, expect_script_name):
    app = MagicMock()
    middleware = PrefixMiddleware(app, prefix="/")
    environ = {
        'PATH_INFO': path_info,
        'SCRIPT_NAME': ""
    }
    middleware(environ, sentinel.start_response)
    app.assert_called_once_with(
        {
            'PATH_INFO': expect_path,
            'SCRIPT_NAME': expect_script_name
        },
        sentinel.start_response
    )


# tests involving /slivka prefix

dataset = [
    # (path_info, expect_path, expect_script_name)
    ("/", "/", ""),
    ("/slivka", "", "/slivka"),
    ("/slivka/", "/", "/slivka"),
    ("/api_1_10/jobs/", "/api_1_10/jobs/", ""),
    ("/slivka/api/query/", "/api/query/", "/slivka"),
    ("/slivka///api/job", "///api/job", "/slivka"),
    ("///slivka", "///slivka", ""),
    ("///", "///", "")
]


@pytest.mark.parametrize(
    ('path_info', 'expect_path', 'expect_script_name'),
    dataset
)
def test_single_part_prefix(path_info, expect_path, expect_script_name):
    app = MagicMock()
    middleware = PrefixMiddleware(app, prefix='slivka')
    environ = {
        'PATH_INFO': path_info,
        'SCRIPT_NAME': ""
    }
    middleware(environ, sentinel.start_response)
    app.assert_called_once_with(
        {
            'PATH_INFO': expect_path,
            'SCRIPT_NAME': expect_script_name
        },
        sentinel.start_response
    )


@pytest.mark.parametrize(
    ('path_info', 'expect_path', 'expect_script_name'),
    dataset
)
def test_leading_slash_ignored(path_info, expect_path, expect_script_name):
    app = MagicMock()
    middleware = PrefixMiddleware(app, prefix='/slivka')
    environ = {
        'PATH_INFO': path_info,
        'SCRIPT_NAME': ""
    }
    middleware(environ, sentinel.start_response)
    app.assert_called_once_with(
        {
            'PATH_INFO': expect_path,
            'SCRIPT_NAME': expect_script_name
        },
        sentinel.start_response
    )


@pytest.mark.parametrize(
    ('path_info', 'expect_path', 'expect_script_name'),
    dataset
)
def test_trailing_slash_ignored(path_info, expect_path, expect_script_name):
    app = MagicMock()
    middleware = PrefixMiddleware(app, prefix="slivka/")
    environ = {
        'PATH_INFO': path_info,
        'SCRIPT_NAME': ""
    }
    middleware(environ, sentinel.start_response)
    app.assert_called_once_with(
        {
            'PATH_INFO': expect_path,
            'SCRIPT_NAME': expect_script_name
        },
        sentinel.start_response
    )


# tests involving /prod/slivka prefix

dataset = [
    # (path_info, expect_path, expect_script_name)
    ("/", "/", ""),
    ("/slivka", "/slivka", ""),
    ("/slivka/", "/slivka/", ""),
    ("/prod", "/prod", ""),
    ("/prod/slivka", "", "/prod/slivka"),
    ("/prod/slivka/", "/", "/prod/slivka"),
    ("//prod/slivka", "//prod/slivka", ""),
    ("/prod/slivka/api", "/api", "/prod/slivka"),
    ("/prod/slivka/api/", "/api/", "/prod/slivka"),
    ("/prod/slivka///api", "///api", "/prod/slivka"),
    ("/prod//slivka/resources", "/prod//slivka/resources", "")
]


@pytest.mark.parametrize(
    ('path_info', 'expect_path', 'expect_script_name'),
    dataset
)
def test_multi_part_prefix(path_info, expect_path, expect_script_name):
    app = MagicMock()
    middleware = PrefixMiddleware(app, prefix="/prod/slivka")
    environ = {
        'PATH_INFO': path_info,
        'SCRIPT_NAME': ""
    }
    middleware(environ, sentinel.start_response)
    app.assert_called_once_with(
        {
            'PATH_INFO': expect_path,
            'SCRIPT_NAME': expect_script_name
        },
        sentinel.start_response
    )
