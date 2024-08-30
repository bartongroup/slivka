import collections.abc
import json
import os.path
import re
import typing
from collections.abc import Sequence
from typing import List, Dict

from packaging.version import parse as parse_version

from slivka.compat import resources
from slivka.utils.env import expandvars

try:
    from typing import get_origin, get_args
except ImportError:
    def get_origin(cls): return getattr(cls, '__origin__', None)
    def get_args(cls): return getattr(cls, '__args__', None)

import attr
import jsonschema
import yaml
from attr import attrs, attrib
from frozendict import frozendict
from jsonschema import Draft7Validator

from slivka.utils import ConfigYamlLoader, flatten_mapping, unflatten_mapping


class ImproperlyConfigured(Exception):
    pass


compatible_config_ver = [
    "0.3",
    "0.8",
    "0.8.0",
    "0.8.1",
    "0.8.2",
    "0.8.3",
    "0.8.4",
    "0.8.5",
]


def load_settings_0_3(config, home=None) -> 'SlivkaSettings':
    home = home or os.getenv('SLIVKA_HOME', os.getcwd())
    home = os.path.realpath(home)
    version = parse_version(config["version"])
    if version.base_version not in compatible_config_ver:
        raise ImproperlyConfigured("Expected config version 0.8")
    config = flatten_mapping(config)
    config_schema = json.loads(resources.read_text(
        "slivka.conf", "settings-schema.json"))
    try:
        jsonschema.validate(config, config_schema, Draft7Validator)
    except jsonschema.ValidationError as e:
        raise ImproperlyConfigured(
            'Error in settings file at \'{path}\'. {reason}'.format(
                path='.'.join(e.path), reason=e.message
            )
        )
    config['directory.home'] = os.path.abspath(home)
    for key, value in config.items():
        if key.startswith('directory.'):
            path = os.path.realpath(os.path.join(home, value))
            config[key] = path

    service_schema = json.loads(resources.read_text(
        "slivka.conf", "service-schema.json"))
    services_dir = config['directory.services']
    services = config['services'] = []
    for fn in os.listdir(services_dir):
        fnmatch = re.match(r'([a-zA-Z0-9_\-.]+)\.service\.ya?ml$', fn)
        if not fnmatch:
            continue
        fn = os.path.join(services_dir, fn)
        srvc_conf = yaml.load(open(fn), ConfigYamlLoader)
        try:
            jsonschema.validate(srvc_conf, service_schema, Draft7Validator)
        except jsonschema.ValidationError as e:
            raise ImproperlyConfigured(
                'Error in file "{file}" at \'{path}\'. {reason}'.format(
                    file=fn, path='/'.join(map(str, e.path)), reason=e.message
                )
            )
        srvc_conf['id'] = fnmatch.group(1)
        services.append(srvc_conf)
    config = unflatten_mapping(config)
    return _deserialize(SlivkaSettings, config)


def load_settings_0_8(config, home=None):
    return load_settings_0_3(config, home=home)


def _deserialize(cls, obj):
    if obj is None:
        return obj
    if attr.has(cls):
        if isinstance(obj, cls):
            return obj
        elif not isinstance(obj, collections.abc.Mapping):
            raise TypeError(
                "Cannot deserialize type '%s' to '%s'" % (type(obj), cls)
            )
        kwargs = {
            re.sub(r'[- ]', '_', key): val for key, val in obj.items()
        }
        fields = attr.fields_dict(cls)
        for key, val in kwargs.items():
            try:
                attribute = fields[key]
            except KeyError:
                continue
            if attribute.type is not None:
                kwargs[key] = _deserialize(attribute.type, val)
        return cls(**kwargs)
    if get_origin(cls) is None:
        return obj
    if issubclass(get_origin(cls), typing.Sequence):
        cls = cls.__args__[0]
        if (isinstance(obj, typing.Mapping) and
                attr.has(cls) and
                attr.fields(cls)[0].name == 'id'):
            for key, val in obj.items():
                val.setdefault('id', key)
            obj = list(obj.values())
        if not isinstance(obj, typing.Sequence):
            raise TypeError('%r is not a sequence' % obj)
        return [_deserialize(cls, val) for val in obj]
    if issubclass(get_origin(cls), typing.Mapping):
        cls = cls.__args__[1]
        if not isinstance(obj, typing.Mapping):
            raise TypeError("%r is not a mapping" % obj)
        if attr.has(cls) and attr.fields(cls)[0].name == 'id':
            for key, val in obj.items():
                val.setdefault('id', key)
        return {key: _deserialize(cls, val) for key, val in obj.items()}
    return obj


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
            id = attr.ib(type=str)
            type = attr.ib(type=str)
            parameters = attr.ib(type=dict, factory=dict)
            consts = attr.ib(type=dict, factory=dict)
            env = attr.ib(type=dict, factory=dict)
            selector_options = attr.ib(type=dict, factory=dict)

        runners = attr.ib(type=Dict[str, Runner])
        selector = attr.ib(type=str, default=None)

    @attrs
    class ServiceTest:
        applicable_runners = attrib(type=List[str])
        parameters = attrib(type=Dict[str, str], converter=_parameters_converter)
        timeout = attrib(type=int, default=None)
        interval = attrib(type=int, default=None)

    id = attrib(type=str)
    slivka_version = attr.ib(converter=parse_version)
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


@attrs(kw_only=True)
class SlivkaSettings:
    @attrs
    class Directory:
        home = attrib()
        uploads = attrib(default="./uploads")
        jobs = attrib(default="./jobs")
        logs = attrib(default="./logs")
        services = attrib(default="./services")

    @attrs
    class Server:
        prefix = attrib(default=None)
        host = attrib(default="127.0.0.1:4040")
        uploads_path = attrib(default="/uploads")
        jobs_path = attrib(default="/jobs")

    @attrs
    class LocalQueue:
        host = attrib(default="127.0.0.1:4041")

    @attrs
    class MongoDB:
        host = attrib(default=None)
        socket = attrib(default=None)
        username = attrib(default=None)
        password = attrib(default=None)
        database = attrib(default="slivka")

    settings_file = attrib(default=None, init=False)
    version = attrib(type=str)
    directory = attrib(type=Directory)
    server = attrib(type=Server)
    local_queue = attrib(type=LocalQueue)
    mongodb = attrib(type=MongoDB)
    services = attrib(type=List[ServiceConfig])


class ServiceSyntaxException(Exception):
    def __init__(self, message, path: Sequence):
        self.message = message
        self.path = path
