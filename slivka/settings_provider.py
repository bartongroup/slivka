import logging.config
import os.path
import sys
from configparser import ConfigParser

import jsonschema
import warnings
import yaml

from slivka.utils import FORM_VALIDATOR, COMMAND_VALIDATOR


class ImproperlyConfigured(Exception):
    pass


class LazySettings:

    def __init__(self):
        self._settings = None

    def __getattr__(self, item):
        if self._settings is None:
            self._setup()
        return getattr(self._settings, item)

    def _setup(self):
        settings_file = os.environ.get("SLIVKA_SETTINGS")
        if not settings_file:
            raise ImproperlyConfigured(
                'Settings are not configured. You must set the environment '
                'variable SLIVKA_SETTINGS.'
            )
        with open(settings_file) as f:
            options = yaml.load(f).items()
        self._settings = SettingsProvider(options)

    def configure(self, **options):
        if self._settings is not None:
            warnings.warn("Settings already configured")
        self._settings = type('Settings', (), {})()
        for name, value in options.items():
            setattr(self._settings, name, value)


class SettingsProvider:

    def __init__(self, options):
        for name, value in options:
            if name.isupper():
                setattr(self, name, value)
        self._service_configs = {}

        # check if all required fields are present
        required_options = ['BASE_DIR', 'MEDIA_DIR', 'WORK_DIR', 'SERVICES_INI',
                            'QUEUE_HOST', 'QUEUE_PORT', 'DATABASE_URL']
        for option in required_options:
            if not hasattr(self, option):
                raise ImproperlyConfigured(
                    '%s is missing from settings' % option
                )

        # join paths with BASE_DIR
        self.BASE_DIR = os.path.abspath(self.BASE_DIR)
        self.MEDIA_DIR = norm_join_path(self.BASE_DIR, self.MEDIA_DIR)
        self.WORK_DIR = norm_join_path(self.BASE_DIR, self.WORK_DIR)
        for path in [self.MEDIA_DIR, self.WORK_DIR]:
            os.makedirs(path, exist_ok=True)
        self.SERVICES_INI = norm_join_path(self.BASE_DIR, self.SERVICES_INI)

        # load services configurations
        services_config = ConfigParser()
        services_config.optionxform = lambda opt: opt
        with open(self.SERVICES_INI) as f:
            services_config.read_file(f)
        for section in services_config.sections():
            form_file = services_config.get(section, 'form')
            command_file = services_config.get(section, 'config')
            self._service_configs[section] = (
                ServiceConfigurationProvider(
                    service=section,
                    form_file=os.path.join(self.BASE_DIR, form_file),
                    command_file=os.path.join(self.BASE_DIR, command_file)
                )
            )

        # configure logging
        os.makedirs('logs', exist_ok=True)
        logging.config.dictConfig(_LOGGER_CONFIG_TEMPLATE)

    @property
    def service_configurations(self):
        return self._service_configs

    def get_service_configuration(self, service):
        return self._service_configs[service]

    @property
    def services(self):
        return list(self._service_configs.keys())


def norm_join_path(*args):
    return os.path.normpath(os.path.join(*args))


class ServiceConfigurationProvider:

    def __init__(self, service, form_file, command_file):
        self._service = service

        with open(form_file, 'r') as f:
            form = yaml.load(f)
        try:
            FORM_VALIDATOR.validate(form)
        except jsonschema.exceptions.ValidationError as exc:
            logging.error(
                'Error validating form definition file %s', form_file
            )
            print('\n', exc, sep='')
            sys.exit(1)
        else:
            self._form = form

        with open(command_file, 'r') as f:
            config = yaml.load(f)
        try:
            COMMAND_VALIDATOR.validate(config)
            self._execution_config = config
        except jsonschema.exceptions.ValidationError as exc:
            logging.exception(
                'Error validating configuration file %s', form_file
            )
            print('\n', exc, sep='')
            sys.exit(1)
        else:
            self._execution_config = config

    @property
    def service(self):
        return self._service

    @property
    def form(self):
        return self._form

    @property
    def execution_config(self):
        return self._execution_config

    def __repr__(self):
        return '<%s ConfigurationProvider>' % self._service


_LOGGER_CONFIG_TEMPLATE = {
    "version": 1,
    "root": {
        "level": "DEBUG",
        "handlers": ["console"]
    },
    "loggers": {
        "slivka.scheduler.scheduler": {
            "level": "DEBUG",
            "propagate": True,
            "handlers": ["scheduler_file"]
        },
        "slivka.scheduler.task_queue": {
            "level": "DEBUG",
            "propagate": True,
            "handlers": ["task_queue_file"]
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "minimal",
            "level": "INFO",
            "stream": "ext://sys.stdout"
        },
        "scheduler_file": {
            "class": "logging.FileHandler",
            "formatter": "default",
            "level": "DEBUG",
            "filename": os.path.join('logs', 'scheduler.log'),
            "encoding": "utf-8"
        },
        "task_queue_file": {
            "class": "logging.FileHandler",
            "formatter": "default",
            "level": "DEBUG",
            "filename": os.path.join('logs', 'queue.log'),
            "encoding": "utf-8"
        }
    },
    "formatters": {
        "default": {
            "format": "%(asctime)s %(name)s %(levelname)s: %(message)s",
            "datefmt": "%d %b %H:%M:%S"
        },
        "minimal": {
            "format": "%(levelname)s: %(message)s"
        }
    }
}

#
# class SettingsProvider2:
#
#     def __init__(self):
#         self._settings = {}
#         self._service_configurations = {}
#
#     def get(self, item):
#         return self._settings[item]
#
#     def set(self, item, value):
#         self._settings[item] = value
#
#     def __getattr__(self, item):
#         return self.get(item)
#
#     def __getitem__(self, item):
#         return self.get(item)
#
#     def __setitem__(self, key, value):
#         self.set(key, value)
#
#     @property
#     def service_configurations(self):
#         """
#         :rtype: dict[str, ServiceConfigurationProvider]
#         """
#         return self._service_configurations
#
#     def get_service_configuration(self, service):
#         """
#         :rtype: ServiceConfigurationProvider
#         """
#         return self._service_configurations[service]
#
#     @property
#     def services(self):
#         return list(self._service_configurations.keys())
#
#     def init_logs(self):
#         self['LOGS_DIR'] = _LOGS_DIR
#         self['LOGGER_CONFIG'] = _LOGGER_CONFIG_TEMPLATE.copy()
#         os.makedirs('logs', exist_ok=True)
#
#     def read_yaml_file(self, filename):
#         with open(filename, 'r') as f:
#             raw = yaml.load(f)
#         items = {
#             key.upper(): value for key, value in raw.items()
#         }
#         self.read_dict(items)
#
#     def read_ini_file(self, filename):
#         def _headless_file_wrapper(path):
#             yield '[slivka]\n'
#             with open(path) as f:
#                 yield from f
#         parser = ConfigParser()
#         parser.optionxform = str.upper
#         parser.read_file(_headless_file_wrapper(filename))
#         self.read_dict(parser['slivka'])
#
#     def read_dict(self, items):
#         self._settings.update(items)
#         self._sanitize_paths()
#         self._create_service_configurations(
#             self._load_services_ini(self.SERVICES_INI)
#         )
#
#     def _sanitize_paths(self):
#         """Join all directory paths with ``BASE_DIR``"""
#         self['BASE_DIR'] = os.path.abspath(self.BASE_DIR)
#         for key, value in self._settings.items():
#             if key.endswith('_DIR') and key != 'BASE_DIR':
#                 self[key] = os.path.abspath(os.path.join(self.BASE_DIR, value))
#                 os.makedirs(self[key], exist_ok=True)
#         self['SERVICES_INI'] = os.path.abspath(
#             os.path.join(self.BASE_DIR, self.SERVICES_INI))
#
#     @staticmethod
#     def _load_services_ini(path):
#         service_config = ConfigParser()
#         service_config.optionxform = lambda option: option
#         with open(path) as f:
#             service_config.read_file(f)
#         return service_config
#
#     def _create_service_configurations(self, parser):
#         """
#         :param parser: config parser pre-loaded with ``service.ini``
#         :type parser: ConfigParser
#         """
#         for section in parser.sections():
#             self._service_configurations[section] = (
#                 ServiceConfigurationProvider(
#                     service=section,
#                     form_file=os.path.join(
#                         self.BASE_DIR, parser.get(section, 'form')),
#                     command_file=os.path.join(
#                         self.BASE_DIR, parser.get(section, 'config'))
#                 )
#             )

