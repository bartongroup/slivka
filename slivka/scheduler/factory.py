from importlib import import_module
from typing import Type, Tuple, Callable, List

import slivka.scheduler.runners
from slivka.conf import ServiceConfig
from slivka.scheduler.runners import RunnerID, Runner
from slivka.scheduler.scheduler import SelectorMeta, BaseSelector


def runners_from_config(config: ServiceConfig) -> Tuple[Callable, List[Runner]]:
    selector_cp = config.execution.selector
    if selector_cp is not None:
        mod, attr = selector_cp.rsplit('.', 1)
        selector = getattr(import_module(mod), attr)
        if isinstance(selector, SelectorMeta):
            selector = selector()
    else:
        selector = BaseSelector.default
    runners = []
    for runner_conf in config.execution.runners.values():
        if '.' in runner_conf.type:
            mod, attr = runner_conf.type.rsplit('.', 1)
            cls: Type[Runner] = getattr(import_module(mod), attr)
        else:
            cls: Type[Runner] = getattr(slivka.scheduler.runners, runner_conf.type)
        # noinspection PyArgumentList
        runner = cls(
            RunnerID(config.id, runner_conf.id),
            command=config.command,
            args=config.args,
            consts=runner_conf.consts,
            outputs=config.outputs,
            env={**config.env, **runner_conf.env},
            **runner_conf.parameters
        )
        runners.append(runner)
    return selector, runners


# TODO: runner tests
