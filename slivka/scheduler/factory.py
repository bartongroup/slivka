import copy
from importlib import import_module
from typing import Type, Tuple, Callable, List

import slivka.scheduler.runners
from scheduler import BaseCommandRunner
from scheduler.starter import CommandStarter, RunnerID
from slivka.conf import ServiceConfig
from slivka.scheduler.scheduler import SelectorMeta, BaseSelector


def runners_from_config(config: ServiceConfig) -> Tuple[Callable, List[CommandStarter]]:
    selector_cp = config.execution.selector
    if selector_cp is not None:
        mod, attr = selector_cp.rsplit('.', 1)
        selector = getattr(import_module(mod), attr)
        if isinstance(selector, SelectorMeta):
            selector = selector()
    else:
        selector = BaseSelector.default

    base_starter = CommandStarter(
        RunnerID(config.id, None),
        base_command=config.command,
        args=config.args,
        env=config.env
    )
    starters = []
    for runner_config in config.execution.runners.values():
        if '.' in runner_config.type:
            mod, attr = runner_config.type.rsplit('.', 1)
            cls: Type[BaseCommandRunner] = getattr(import_module(mod), attr)
        else:
            cls: Type[BaseCommandRunner] = getattr(
                slivka.scheduler.runners, runner_config.type)
        starter = copy.copy(base_starter)
        starter.id = RunnerID(config.id, runner_config.id)
        # noinspection PyArgumentList
        starter.runner = cls(**runner_config.parameters)
        starters.append(starter)
    return selector, starters


# TODO: runner tests
