import json
import os.path
from collections.abc import Mapping
from urllib.parse import quote_plus

import attr
import jsonschema
import pkg_resources
import yaml
from jsonschema import Draft4Validator

from slivka.utils import SafeTranscludingOrderedYamlLoader, cached_property


class ImproperlyConfigured(Exception):
    pass


def SettingsVer1Loader(filename) -> "Settings":
    with open(filename) as f:
        conf = yaml.safe_load(f)
    return Settings(
        base_dir=conf['BASE_DIR'],
        uploads_dir=conf['UPLOADS_DIR'],
        jobs_dir=conf['JOBS_DIR'],
        logs_dir=conf['LOG_DIR'],
        services_config_file=conf['SERVICES'],
        server_host=conf['SERVER_HOST'],
        server_port=conf['SERVER_PORT'],
        uploads_url_path=conf['UPLOADS_URL_PATH'],
        jobs_url_path=conf['JOBS_URL_PATH'],
        url_prefix=conf.get('URL_PREFIX'),
        accepted_media_types=conf['ACCEPTED_MEDIA_TYPES'],
        slivka_queue_address=conf['SLIVKA_QUEUE_ADDR'],
        mongodb=conf.get('MONGODB') or conf.get('MONGODB_ADDR'),
        secret_key=conf.get('SECRET_KEY')
    )


class SettingsProxy:
    settings_file = None

    def __init__(self):
        self.loader = SettingsVer1Loader

    @cached_property
    def settings(self) -> "Settings":
        settings_file = self.settings_file or os.environ.get("SLIVKA_SETTINGS")
        if not settings_file:
            raise ImproperlyConfigured(
                'Settings are not configured. You must set the environment '
                'variable SLIVKA_SETTINGS.'
            )
        return self.loader(settings_file)

    def __getattr__(self, item):
        val = getattr(self.settings, item)
        self.__dict__[item] = val
        return val


settings = SettingsProxy()


def _path_normalizer(self: 'Settings', attrib: attr.Attribute, val):
    path = os.path.normpath(os.path.join(self.base_dir, val))
    if not os.path.exists(path):
        os.mkdir(path)
    setattr(self, attrib.name, path)


def _mongodb_converter(val):
    if isinstance(val, str):
        url, database = val.rsplit('/', 1)
    elif isinstance(val, Mapping):
        url = "mongodb://"
        if 'username' in val:
            if 'password' in val:
                url += '%s:%s@' % (quote_plus(val['username']), quote_plus(val['password']))
            else:
                url += '%s@' % quote_plus(val['username'])
        if 'host' in val:
            url += val['host']
        elif 'socket' in val:
            url += quote_plus(val['socket'])
        else:
            raise KeyError("No 'host' or 'socket' specified")
        database = val['database']
    else:
        raise TypeError
    return url, database


def _services_factory(self: 'Settings'):
    with open(self.services_config_file) as fp:
        data = yaml.safe_load(fp)
    root = self.base_dir
    return {
        name: ServiceInfo(
            name=name,
            label=section['label'],
            form=os.path.join(root, section['form']),
            command=os.path.join(root, section['command']),
            presets=(os.path.join(root, section['presets'])
                     if 'presets' in section else None),
            classifiers=section.get('classifiers', [])
        )
        for name, section in data.items()
    }


@attr.s
class Settings:
    base_dir = attr.ib(type=str, converter=os.path.abspath)
    uploads_dir = attr.ib(type=str, validator=_path_normalizer)
    jobs_dir = attr.ib(type=str, validator=_path_normalizer)
    logs_dir = attr.ib(type=str, validator=_path_normalizer)
    services_config_file = attr.ib(type=str, validator=_path_normalizer)

    server_host = attr.ib()
    server_port = attr.ib(converter=int)
    uploads_url_path = attr.ib()
    jobs_url_path = attr.ib()
    url_prefix = attr.ib()

    accepted_media_types = attr.ib(type=list)
    slivka_queue_address = attr.ib()
    mongodb = attr.ib(converter=_mongodb_converter)
    secret_key = attr.ib(default=None)
    services = attr.ib(init=False, default=attr.Factory(_services_factory, True))


def _yaml_settings_loader(filename):
    if filename is None:
        return None
    with open(filename, 'r') as f:
        return yaml.load(f, SafeTranscludingOrderedYamlLoader)


def _json_schema_validator(schema_file):
    schema = json.loads(
        pkg_resources.resource_string("slivka.conf", schema_file).decode()
    )

    def validator(_obj, _attr, val):
        jsonschema.validate(val, schema, Draft4Validator)

    return validator


@attr.s
class ServiceInfo:
    name = attr.ib(type=str)
    label = attr.ib(type=str)
    form = attr.ib(
        converter=_yaml_settings_loader,
        validator=_json_schema_validator("formDefSchema.json")
    )
    command = attr.ib(
        converter=_yaml_settings_loader,
        validator=_json_schema_validator("commandDefSchema.json")
    )
    presets = attr.ib(
        converter=_yaml_settings_loader,
        validator=attr.validators.optional(
            _json_schema_validator("presetsSchema.json")
        )
    )
    classifiers = attr.ib(default=[], type=list)
