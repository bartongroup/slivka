from unittest.mock import MagicMock, sentinel

import pytest

from slivka.server import PrefixMiddleware


datasets = []

empty_prefix_dataset = [
    # (path_info, expect_path, expect_script_name)
    ("/", "/", ""),
    ("/slivka", "/slivka", ""),
    ("/slivka/", "/slivka/", ""),
    ("/api-v1_1/jobs", "/api-v1_1/jobs", ""),
    ("/slivka/api/query/", "/slivka/api/query/", ""),
    ("/slivka///api/job", "/slivka///api/job", ""),
    ("///slivka", "///slivka", ""),
    ("///", "///", ""),
]
datasets.extend(("", *args) for args in empty_prefix_dataset)
datasets.extend(("/", *args) for args in empty_prefix_dataset)

slivka_prefix_dataset = [
    # (path_info, expect_path, expect_script_name)
    ("/", "/", ""),
    ("/slivka", "", "/slivka"),
    ("/slivka/", "/", "/slivka"),
    ("/slivka//", "//", "/slivka"),
    ("/api_1_10/jobs/", "/api_1_10/jobs/", ""),
    ("/prod/slivka/api", "/prod/slivka/api", ""),
    ("/slivka/api/query/", "/api/query/", "/slivka"),
    ("/slivka///api/job", "///api/job", "/slivka"),
    ("///slivka", "///slivka", ""),
    ("///", "///", ""),
]
datasets.extend(("/slivka", *args) for args in slivka_prefix_dataset)
datasets.extend(("slivka", *args) for args in slivka_prefix_dataset)

two_part_prefix_dataset = [
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
    ("/prod//slivka/resources", "/prod//slivka/resources", ""),
]
datasets.extend(("/prod/slivka", *args) for args in two_part_prefix_dataset)
datasets.extend(("prod/slivka", *args) for args in two_part_prefix_dataset)


@pytest.mark.parametrize(
    ("prefix", "path_info", "expect_path", "expect_script_name"), datasets
)
def test_prefix_middleware_environ(prefix, path_info, expect_path, expect_script_name):
    app = MagicMock()
    middleware = PrefixMiddleware(app, prefix=prefix)
    environ = {"PATH_INFO": path_info, "SCRIPT_NAME": ""}
    middleware(environ, sentinel.start_response)
    app.assert_called_once_with(
        {"PATH_INFO": expect_path, "SCRIPT_NAME": expect_script_name},
        sentinel.start_response,
    )
