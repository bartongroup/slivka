from unittest import mock

import pytest

from slivka.scheduler import BaseSelector


class ExampleSelector(BaseSelector):
    def limit_runner1(self, inputs):
        return inputs.get("use") == 1 or inputs.get("use_runner1")

    def limit_runner2(self, inputs):
        return inputs.get("use") == 2 or inputs.get("use_runner2")

    def limit_runner3(self, inputs):
        return inputs.get("use") == 3 or inputs.get("use_runner3")


@pytest.mark.parametrize(
    "inputs, expected",
    [
        ({"use": 1}, "runner1"),
        ({"use": 2}, "runner2"),
        ({"use": 3, "use_runner1": "Y"}, "runner1"),
        ({"use_runner2": "Y", "use_runner3": "Y"}, "runner2"),
        (
            {
                "use_runner1": "Y",
                "use_runner2": "Y",
                "use_runner3": "Y",
                "use": 2,
            },
            "runner1",
        ),
        ({}, None),
        ({"use": -1}, None),
        ({"no_match": True}, None),
    ],
)
def test_selector(inputs, expected):
    selector = ExampleSelector()
    assert selector(inputs) == expected


def test_selector_setup_called():
    selector = ExampleSelector()
    with mock.patch.object(ExampleSelector, "setup") as mock_setup:
        selector({})
        mock_setup.assert_called_once_with({})
