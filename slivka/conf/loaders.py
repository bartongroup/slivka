import json
import os.path
import re
from collections.abc import Mapping
from functools import partial
from importlib import import_module
from urllib.parse import quote_plus

import attr
import jsonschema
import pkg_resources
import yaml
from jsonschema import Draft4Validator

from slivka.utils import SafeTranscludingOrderedYamlLoader


class ImproperlyConfigured(Exception):
    pass


class SettingsLoaderV10:
    def __call__(self):
        settings_path = (
            os.getenv('SLIVKA_SETTINGS') or
            next((fn for fn in os.listdir('.')
                  if re.match(r'settings\.ya?ml', fn)), None)
        )
        if settings_path is None:
            raise ImproperlyConfigured(
                'Settings are not configured. You must set the SLIVKA_SETTINGS '
                'environment variable or create a settings.yaml file in '
                'the current working directory.'
            )
        with open(settings_path) as f:
            conf = yaml.safe_load(f)
        root = os.path.join(os.path.dirname(settings_path), conf['BASE_DIR'])
        return Settings(
            base_dir=conf['BASE_DIR'],
            uploads_dir=_prepare_dir(root, conf['UPLOADS_DIR']),
            jobs_dir=_prepare_dir(root, conf['JOBS_DIR']),
            logs_dir=_prepare_dir(root, conf['LOG_DIR']),
            services=self._load_services(root, conf['SERVICES']),
            server_host=conf['SERVER_HOST'],
            server_port=conf['SERVER_PORT'],
            uploads_url_path=conf['UPLOADS_URL_PATH'],
            jobs_url_path=conf['JOBS_URL_PATH'],
            url_prefix=conf.get('URL_PREFIX'),
            accepted_media_types=conf['ACCEPTED_MEDIA_TYPES'],
            slivka_queue_address=conf['SLIVKA_QUEUE_ADDR'],
            mongodb=conf.get('MONGODB') or conf.get('MONGODB_ADDR'),
            secret_key=conf.get('SECRET_KEY'),
        )

    @staticmethod
    def _load_services(root, services_file):
        with open(os.path.join(root, services_file)) as f:
            data = yaml.safe_load(f)

        def load_yaml(fn):
            fp = os.path.join(root, fn)
            return yaml.load(open(fp, 'r'), SafeTranscludingOrderedYamlLoader)

        return {
            name: Service(
                name=name,
                label=service['label'],
                form=load_yaml(service['form']),
                command=load_yaml(service['command']),
                presets=(load_yaml(service['presets'])
                         if 'presets' in service else None),
                classifiers=service.get('classifiers', [])
            )
            for name, service in data.items()
        }


class SettingsLoaderV11:
    def __call__(self):
        root = os.getenv('SLIVKA_HOME', os.getcwd())
        fp = os.path.join(root, 'settings.yaml')
        if not os.path.isfile(fp):
            fp = os.path.join(root, 'settings.yml')
        conf = yaml.safe_load(open(fp))
        return Settings(
            base_dir=root,
            uploads_dir=_prepare_dir(root, conf['UPLOADS_DIR']),
            jobs_dir=_prepare_dir(root, conf['JOBS_DIR']),
            logs_dir=_prepare_dir(root, conf['LOG_DIR']),
            services=dict(self._load_services(root, conf['SERVICES'])),
            server_host=conf['SERVER_HOST'],
            server_port=conf['SERVER_PORT'],
            uploads_url_path=conf['UPLOADS_URL_PATH'],
            jobs_url_path=conf['JOBS_URL_PATH'],
            url_prefix=conf.get('URL_PREFIX'),
            accepted_media_types=conf.get('ACCEPTED_MEDIA_TYPES', []),
            slivka_queue_address=conf['SLIVKA_QUEUE_ADDR'],
            mongodb=conf.get('MONGODB') or conf.get('MONGODB_ADDR'),
            secret_key=conf.get('SECRET_KEY'),
        )

    @staticmethod
    def _load_services(root, conf_dir):
        pattern = re.compile(r'[\w_-]*\.service\.ya?ml')
        conf_dir = os.path.join(root, conf_dir)
        for fn in filter(pattern.match, os.listdir(conf_dir)):
            fp = os.path.join(conf_dir, fn)
            conf = yaml.load(open(fp), SafeTranscludingOrderedYamlLoader)
            name = str.split(fn, '.', maxsplit=1)[0]
            command = conf['command']
            command.update(runners=conf['runners'])
            if 'limiter' in conf:
                command.update(limiter=conf['limiter'])
            yield name, Service(
                name=name,
                label=conf['label'],
                classifiers=conf['classifiers'],
                form=conf['form'],
                command=command,
                presets=conf.get('presets')
            )


def _prepare_dir(root, path):
    path = os.path.normpath(os.path.join(root, path))
    os.makedirs(path, exist_ok=True)
    return path


def _mongodb_converter(val):
    if isinstance(val, str):
        url, database = val.rsplit('/', 1)
    elif isinstance(val, Mapping):
        url = "mongodb://"
        if 'username' in val:
            if 'password' in val:
                url += '%s:%s@' % (
                    quote_plus(val['username']), quote_plus(val['password'])
                )
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


@attr.s
class Settings:
    base_dir = attr.ib(type=str, converter=os.path.abspath)
    uploads_dir = attr.ib(type=str)
    jobs_dir = attr.ib(type=str)
    logs_dir = attr.ib(type=str)

    server_host = attr.ib()
    server_port = attr.ib(converter=int)
    uploads_url_path = attr.ib()
    jobs_url_path = attr.ib()
    url_prefix = attr.ib()

    accepted_media_types = attr.ib(type=list)
    slivka_queue_address = attr.ib()
    mongodb = attr.ib(converter=_mongodb_converter)
    services = attr.ib()
    secret_key = attr.ib(default=None)


def _form_validator(_obj, _attr, val):
    basic_schema = json.loads(pkg_resources.resource_string(
        "slivka.conf", "any-field-schema.json").decode())
    from slivka.server.forms import fields
    classes = {
        "int": fields.IntegerField,
        "float": fields.DecimalField,
        "decimal": fields.DecimalField,
        "text": fields.TextField,
        "boolean": fields.BooleanField,
        "flag": fields.FlagField,
        "choice": fields.ChoiceField,
        "file": fields.FileField,
    }
    for field in val.values():
        jsonschema.validate(field, basic_schema, Draft4Validator)
        field_type = field['value']['type']
        cls = classes.get(field_type)
        if cls is None:
            try:
                mod, attrib = field_type.rsplit('.', 1)
                cls = getattr(import_module(mod), attrib)
            except (ValueError, AttributeError):
                raise ValueError("Invalid field type %s" % field_type)
        jsonschema.validate(field, cls.schema)


def _json_schema_validator(schema_file):
    schema = json.loads(pkg_resources.resource_string(
        "slivka.conf", schema_file).decode())

    def validator(_obj, _attr, val): jsonschema.validate(val, schema, Draft4Validator)
    return validator


@attr.s
class Service:
    name = attr.ib(type=str)
    label = attr.ib(type=str)
    form = attr.ib(validator=_form_validator)
    command = attr.ib(validator=_json_schema_validator("commandDefSchema.json"))
    presets = attr.ib(validator=attr.validators.optional(
        _json_schema_validator("presetsSchema.json")
    ))
    classifiers = attr.ib(factory=list, type=list)
