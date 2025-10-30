import collections.abc
import json
import os.path
import re
from typing import Dict, List, Type, Optional

import attr
import jsonschema
import ruamel.yaml
from attr import attrs, attrib
from frozendict import frozendict
from jsonschema.validators import Draft7Validator
from packaging.version import parse as parse_version

from slivka.compat import resources
from slivka.utils.env import expandvars


@attrs(slots=True, frozen=True)
class ServiceConfigError(ValueError):
    path = attrib(type=List[str])
    message = attrib(type=str)

    @property
    def path_string(self):
        return "/" + "/".join(self.path)


class ServiceYAMLLoader(ruamel.yaml.YAML):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.constructor.add_constructor("!include", self._include_constructor)

    @staticmethod
    def _include_constructor(constructor, node):
        loader = constructor.loader
        root_path = os.path.realpath(
            os.path.dirname(loader.reader.name) if loader.reader.name else os.getcwd()
        )
        value = constructor.construct_scalar(node)
        # value can be either <file> or <file>::<node_path>
        value = value.split("::", maxsplit=1)
        file_name, node_path = value if len(value) == 2 else (value[0], "/")
        file_path = os.path.join(root_path, file_name)
        yaml_loader = type(loader)(typ=loader.typ, pure=loader.pure)
        with open(file_path, "r") as f:
            obj = yaml_loader.load(f)
        for key in filter(None, node_path.split("/")):
            obj = obj[key]
        return obj


def read_yaml(path):
    basename = os.path.basename(path)
    basename, pri_ext = os.path.splitext(basename)
    basename, sec_ext = os.path.splitext(basename)
    if (
        not basename
        or (pri_ext != ".yaml" and pri_ext != ".yml")
        or sec_ext != ".service"
    ):
        raise ValueError(
            f"Invalid service file name: {basename}. "
            f"The name must end with '.service.yaml'"
        )
    if m := re.search(r"[^a-zA-Z0-9_\-.]", basename):
        raise ValueError(
            f"Invalid service file name: {basename}. "
            f"It contains an illegal character {m.group()}"
        )
    with open(path, 'rb') as f:
        config_dict = ServiceYAMLLoader().load(f)
    return read_dict(basename, config_dict)


def read_dict(service_id, config_dict) -> 'ServiceConfig':
    with resources.open_text(__package__, "service-schema.json") as f:
        schema = json.load(f)
    try:
        jsonschema.validate(config_dict, schema, Draft7Validator)
    except jsonschema.ValidationError as e:
        raise ServiceConfigError(list(map(str, e.path)), e.message)

    kwargs = config_dict.copy()

    kwargs["parameters"] = {
        key: _parse_parameter(val)
        for key, val in config_dict["parameters"].items()
    }
    kwargs["args"] = [
        _parse_attrs_dict(ServiceConfig.Argument, key, val)
        for key, val in config_dict["args"].items()
    ]
    kwargs["outputs"] = [
        _parse_attrs_dict(ServiceConfig.OutputFile, key, val)
        for key, val in config_dict["outputs"].items()
    ]

    execution_dict_obj = config_dict["execution"]
    runners = {
        key: _parse_attrs_dict(ServiceConfig.Execution.Runner, key, val)
        for key, val in execution_dict_obj["runners"].items()
    }
    execution_dict_obj["runners"] = runners
    kwargs["execution"] = _parse_attrs_dict(
        ServiceConfig.Execution, None, execution_dict_obj
    )

    if "tests" in config_dict:
        kwargs["tests"] = [
            _parse_attrs_dict(ServiceConfig.ServiceTest, None, val)
            for val in config_dict["tests"]
        ]

    return _parse_attrs_dict(ServiceConfig, service_id, kwargs)


def _parse_attrs_dict(klass: Type, obj_id: Optional[str], obj_dict: dict):
    kwargs = {
        key.replace('-', '_').replace(' ', '_'): val
        for key, val in obj_dict.items()
    }
    if hasattr(attr.fields(klass), "id"):
        kwargs.setdefault("id", obj_id)
    return klass(**kwargs)


def _parse_parameter(data_dict: dict):
    remaining_kwargs = data_dict.copy()
    kwargs = {}
    for attribute in attr.fields(ServiceConfig.Parameter):
        try:
            kwargs[attribute.alias] = remaining_kwargs.pop(attribute.alias)
        except KeyError:
            continue
    kwargs["constraints"] = remaining_kwargs
    return ServiceConfig.Parameter(**kwargs)


def _parameters_converter(parameters: dict):
    converted = {}
    for key, val in parameters.items():
        if isinstance(val, str):
            converted[key] = expandvars(val)
        elif isinstance(val, list):
            converted[key] = [expandvars(v) for v in val]
        else:
            raise ValueError(
                "Invalid parameter type %r. Only list or str are allowed"
                % type(val)
            )
    return converted


@attrs(kw_only=True)
class ServiceConfig:
    @attrs
    class Parameter(collections.abc.Mapping):
        # parameters dict didn't store the id in dict values
        # id = attrib(type=str)
        type = attrib(type=str)
        name = attrib(type=str)
        description = attrib(type=str, default="")
        default = attrib(default=None)
        required = attrib(type=bool, default=True, converter=attr.converters.to_bool)
        condition = attrib(type=str, default=None)
        _constraints = attrib(type=dict, factory=dict)

        def __getitem__(self, item):
            try:
                return getattr(self, item)
            except AttributeError:
                return self._constraints[item]

        def __iter__(self):
            yield from (
                attribute.name for attribute in attr.fields(type(self))
                if not attribute.name.startswith("_")
            )
            yield from self._constraints

        def __len__(self):
            # count the number of elements yielded by __iter__
            return sum(1 for _ in self)

    @attrs
    class Argument:
        id = attrib(type=str)
        arg = attrib(type=str)
        symlink = attrib(type=str, default=None)
        default = attrib(type=str, default=None)
        join = attrib(type=str, default=None)

    @attrs
    class OutputFile:
        id = attrib(type=str)
        path = attrib(type=str)
        name = attrib(type=str, default="")
        media_type = attrib(type=str, default="")

    @attrs
    class Execution:
        @attrs
        class Runner:
            id = attrib(type=str)
            type = attrib(type=str)
            parameters = attrib(type=dict, factory=dict)
            consts = attrib(type=dict, factory=dict)
            env = attrib(type=dict, factory=dict)
            selector_options = attrib(type=dict, factory=dict)

        runners = attrib(type=Dict[str, Runner])
        selector = attrib(type=str, default=None)

    @attrs
    class ServiceTest:
        applicable_runners = attrib(type=List[str])
        parameters = attrib(type=Dict[str, str], converter=_parameters_converter)
        timeout = attrib(type=int, default=None)
        interval = attrib(type=int, default=None)

    id = attrib(type=str)
    slivka_version = attrib(converter=parse_version)
    name = attrib(type=str)
    description = attrib(type=str, default="")
    author = attrib(type=str, default="")
    version = attrib(type=str, default="")
    license = attrib(type=str, default="")
    classifiers = attrib(type=List[str], factory=list)
    parameters = attrib(type=dict, converter=frozendict)
    command = attrib()
    args = attrib(type=List[Argument])
    env = attrib(type=Dict[str, str], converter=frozendict, factory=dict)
    outputs = attrib(type=List[OutputFile])
    execution = attrib(type=Execution)
    tests = attrib(type=List[ServiceTest], factory=list)
