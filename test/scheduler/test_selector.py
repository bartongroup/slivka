from unittest import mock

import pytest

from slivka.scheduler.scheduler import BaseSelector, SelectorContext


class ExampleSelector(BaseSelector):
    def limit_runner1(self, inputs):
        return inputs.get("use") == 1 or inputs.get("use_runner1")

    def limit_runner2(self, inputs):
        return inputs.get("use") == 2 or inputs.get("use_runner2")

    def limit_runner3(self, inputs):
        return inputs.get("use") == 3 or inputs.get("use_runner3")


class SelectorWithContextData(BaseSelector):
    def limit_runner1(self, inputs, low_bound, up_bound):
        if "val" in inputs:
            return low_bound <= float(inputs.get("val")) < up_bound

    def limit_runner2(self, inputs, low_bound):
        if "val" in inputs:
            return low_bound <= float(inputs.get("val"))


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
    context = SelectorContext(
        service="example",
        runners=["runner1", "runner2", "runner3"],
        runner_options={},
    )
    assert selector(inputs, context) == expected


def test_selector_setup_called():
    selector = ExampleSelector()
    context = SelectorContext(
        service="example",
        runners=["runner1", "runner2", "runner3"],
        runner_options={},
    )
    with mock.patch.object(ExampleSelector, "setup") as mock_setup:
        selector({}, context)
        mock_setup.assert_called_once_with({})


@pytest.mark.parametrize(
    "inputs, expected",
    [
        ({"val": 0.95}, "runner1"),
        ({"val": 1.2}, "runner2"),
        ({"val": -0.4}, None),
    ],
)
def test_selector_with_context(inputs, expected):
    selector = SelectorWithContextData()
    context_data = {
        "runner1": {"low_bound": 0.0, "up_bound": 1.0},
        "runner2": {"low_bound": 1.0},
    }
    context = SelectorContext(
        service="example",
        runners=["runner1", "runner2"],
        runner_options=context_data,
    )
    assert selector(inputs, context) == expected
