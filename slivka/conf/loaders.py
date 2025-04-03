import collections.abc
import json
import os.path
import re
import typing
import warnings
from collections.abc import Sequence
from typing import List, Dict
from urllib.parse import quote_plus, urlunsplit, urlencode, urlsplit

from jsonschema.validators import Draft202012Validator
from packaging.version import parse as parse_version

from slivka.compat import resources

from . import service_loader
from .service_loader import ServiceConfig, ServiceConfigError

try:
    from typing import get_origin, get_args
except ImportError:
    def get_origin(cls): return getattr(cls, '__origin__', None)
    def get_args(cls): return getattr(cls, '__args__', None)

import attr
import jsonschema
import yaml
from attr import attrs, attrib
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
    loader = SettingsLoader_0_8_5b5()
    loader.read_dict({"directory.home": home})
    loader.read_dict(config)
    loader.read_env(os.environ)
    return loader.build()


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
        return cls(**{k: v for k, v in kwargs.items() if k in fields})
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


class SettingsLoader_0_8_5b5:
    def __init__(self):
        self._chain_map = collections.ChainMap()
        self._settings_schema = json.load(
            resources.open_text("slivka.conf", "partial-settings-schema.json")
        )

    def _prepend_config(self, dictionary):
        try:
            jsonschema.validate(dictionary, self._settings_schema, Draft202012Validator)
        except jsonschema.ValidationError as e:
            raise ImproperlyConfigured(
                f"Settings error at '{'.'.join(e.path)}'. {e.message}"
            )
        if "mongodb.host" in dictionary or "mongodb.socket" in dictionary or "mongodb.uri" in dictionary:
            mongo_uri, mongo_database = self._parse_mongodb_config(dictionary)
            dictionary["mongodb.uri"] = mongo_uri
            dictionary["mongodb.database"] = mongo_database
        self._chain_map.maps.insert(0, dictionary)

    def read_dict(self, dictionary):
        self._prepend_config(flatten_mapping(dictionary))

    def read_yaml(self, path):
        with open(path) as f:
            dictionary = yaml.safe_load(f)
        dictionary["settings-file"] = str(path)
        version = parse_version(dictionary["version"])
        if version.base_version not in compatible_config_ver:
            raise ImproperlyConfigured(
                f"File {path} is not compatible with this slivka version."
            )
        self.read_dict(dictionary)

    def read_env(self, env):
        config = {
            config_prop: env[var_name]
            for var_name, config_prop in [
                ("SLIVKA_HOME", "directory.home"),
                ("SLIVKA_DIR_UPLOADS", "directory.uploads"),
                ("SLIVKA_DIR_JOBS", "directory.uploads"),
                ("SLIVKA_SERVER_PREFIX", "server.prefix"),
                ("SLIVKA_SERVER_HOST", "server.host"),
                ("SLIVKA_LOCAL_QUEUE_HOST", "local-queue.host"),
                ("SLIVKA_MONGODB_HOST", "mongodb.host"),
                ("SLIVKA_MONGODB_SOCKET", "mongodb.socket"),
                ("SLIVKA_MONGODB_USERNAME", "mongodb.username"),
                ("SLIVKA_MONGODB_PASSWORD", "mongodb.password"),
                ("SLIVKA_MONGODB_QUERY", "mongodb.query"),
                ("SLIVKA_MONGODB_DATABASE", "mongodb.database"),
                ("SLIVKA_MONGODB_URI", "mongodb.uri"),
            ]
            if var_name in env
        }
        self._prepend_config(config)

    @staticmethod
    def _parse_mongodb_config(dictionary):
        if "mongodb.uri" in dictionary:
            connection_uri = dictionary["mongodb.uri"]
            if "mongodb.database" in dictionary:
                database = dictionary["mongodb.database"]
            else:
                split_result = urlsplit(dictionary["mongodb.uri"])
                database = split_result.path.lstrip("/")
        else:
            options = {
                key.rsplit('.', 1)[-1]: val for key, val in dictionary.items()
                if key.startswith("mongodb.options.")
            }
            connection_uri = _build_mongodb_uri(
                hostname=dictionary.get("mongodb.host"),
                socket=dictionary.get("mongodb.socket"),
                username=dictionary.get("mongodb.username"),
                password=dictionary.get("mongodb.password"),
                query=dictionary.get("mongodb.query"),
                options=options
            )
            database = dictionary["mongodb.database"]
        return connection_uri, database

    def build(self) -> 'SlivkaSettings':
        config = self._chain_map
        home = os.path.realpath(config["directory.home"])
        for key, value in config.items():
            if key.startswith("directory."):
                config[key] = os.path.realpath(os.path.join(home, value))

        services_dir = config["directory.services"]
        services = config['services'] = []
        for fn in os.listdir(services_dir):
            fnmatch = re.match(r'([a-zA-Z0-9_\-.]+)\.service\.ya?ml$', fn)
            if not fnmatch:
                continue
            fn = os.path.join(services_dir, fn)
            try:
                service_config = service_loader.read_yaml(fn)
            except ServiceConfigError as e:
                raise ImproperlyConfigured(
                    f"Error in file '{fn}' at '{e.path_string}': {e.message}"
                )
            services.append(service_config)
        config = unflatten_mapping(config)
        return _deserialize(SlivkaSettings, config)


def _build_mongodb_uri(
        scheme="mongodb",
        hostname=None,
        socket=None,
        username=None,
        password=None,
        query=None,
        options=None,
):
    # >>> For backwards compatibility, will be removed in the future
    if hostname and "?" in hostname:
        hostname, host_query = hostname.split("?", 1)
        query = (f"{host_query}&{query}"
                 if (query and host_query)
                 else (query or host_query))
        warnings.warn(
            "Using query parameters in the host name will be removed in the future. "
            "Use \"mongodb.query\" or \"mongodb.options\" to set query parameters instead.",
            FutureWarning
        )
    if socket and "?" in socket:
        socket, socket_query = socket.split("?", 1)
        query = (f"{socket_query}&{query}"
                 if (query and socket_query)
                 else (query or socket_query))
        warnings.warn(
            "Using query parameters in the socket name will be removed in the future. "
            "Use \"mongodb.query\" or \"mongodb.options\" to set query parameters instead.",
            FutureWarning
        )
    # <<<
    authority = ""
    if username is not None and password is not None:
        authority = f"{quote_plus(username)}:{quote_plus(password)}@"
    elif username is not None:
        authority = f"{quote_plus(username)}@"
    if socket is not None:
        authority += quote_plus(socket)
    elif hostname is not None:
        authority += hostname
    else:
        raise ValueError("Either a 'host' or a 'socket' must be set.")
    if options:
        if query:
            query = f"{query}&{urlencode(options)}"
        else:
            query = urlencode(options)
    return urlunsplit((scheme, authority, "", query, ""))


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
        uri = attrib()
        database = attrib(default="slivka")

    settings_file = attrib(default=None)
    version = attrib(type=str, default=None)
    directory = attrib(type=Directory)
    server = attrib(type=Server)
    local_queue = attrib(type=LocalQueue)
    mongodb = attrib(type=MongoDB)
    services = attrib(type=List[ServiceConfig])


class ServiceSyntaxException(Exception):
    def __init__(self, message, path: Sequence):
        self.message = message
        self.path = path
