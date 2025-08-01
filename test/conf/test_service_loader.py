import pytest

from slivka.compat import resources
from slivka.conf.service_loader import ServiceYAMLLoader


@pytest.mark.parametrize(
    ("file_name", "expected_config"),
    [
        pytest.param(
            "basic_data.yaml",
            {"key1": "value1", "key2": "value2"}
        ),
        pytest.param(
            "include_file_1.yaml",
            {"key1": "val1", "key2": "val2", "key3": "val3"}
        ),
        pytest.param(
            "include_file_2.yaml",
            {"section": {"key1": "val1", "key2": "val2", "key3": "val3"}}
        ),
        pytest.param(
            "include_value_1.yaml",
            {"key1": "val1", "key2": "val2", "key3": "val3"}
        ),
        pytest.param(
            "include_value_2.yaml",
            {"key1": "val1", "key2": "valB"}
        )
    ]
)
def test_yaml_loader(file_name, expected_config):
    with resources.open_binary(__package__, f"data/{file_name}") as f:
        config = ServiceYAMLLoader().load(f)
    assert config == expected_config