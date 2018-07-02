import logging
import os.path
import sys
from configparser import ConfigParser

import jsonschema
import yaml

from slivka.utils import FORM_VALIDATOR, COMMAND_VALIDATOR, Singleton

_LOGS_DIR = 'logs'


class SettingsProvider(metaclass=Singleton):

    def __init__(self):
        self._settings = {}
        self._service_configurations = {}

    def get(self, item):
        return self._settings[item]

    def set(self, item, value):
        self._settings[item] = value

    def __getattr__(self, item):
        return self.get(item)

    def __getitem__(self, item):
        return self.get(item)

    def __setitem__(self, key, value):
        self.set(key, value)

    @property
    def service_configurations(self):
        """
        :rtype: dict[str, ServiceConfigurationProvider]
        """
        return self._service_configurations

    def get_service_configuration(self, service):
        """
        :rtype: ServiceConfigurationProvider
        """
        return self._service_configurations[service]

    @property
    def services(self):
        return list(self._service_configurations.keys())

    def init_logs(self):
        self['LOGS_DIR'] = _LOGS_DIR
        self['LOGGER_CONFIG'] = _LOGGER_CONFIG_TEMPLATE.copy()
        os.makedirs('logs', exist_ok=True)

    def read_yaml_file(self, filename):
        with open(filename, 'r') as f:
            raw = yaml.load(f)
        items = {
            key.upper(): value for key, value in raw.items()
        }
        self.read_dict(items)

    def read_ini_file(self, filename):
        def _headless_file_wrapper(path):
            yield '[slivka]\n'
            with open(path) as f:
                yield from f
        parser = ConfigParser()
        parser.optionxform = str.upper
        parser.read_file(_headless_file_wrapper(filename))
        self.read_dict(parser['slivka'])

    def read_dict(self, items):
        self._settings.update(items)
        self._sanitize_paths()
        self._create_service_configurations(
            self._load_services_ini(self.SERVICES_INI)
        )

    def _sanitize_paths(self):
        """Join all directory paths with ``BASE_DIR``"""
        self['BASE_DIR'] = os.path.abspath(self.BASE_DIR)
        for key, value in self._settings.items():
            if key.endswith('_DIR') and key != 'BASE_DIR':
                self[key] = os.path.abspath(os.path.join(self.BASE_DIR, value))
                os.makedirs(self[key], exist_ok=True)
        self['SERVICES_INI'] = os.path.abspath(
             os.path.join(self.BASE_DIR, self.SERVICES_INI))

    @staticmethod
    def _load_services_ini(path):
        service_config = ConfigParser()
        service_config.optionxform = lambda option: option
        with open(path) as f:
            service_config.read_file(f)
        return service_config

    def _create_service_configurations(self, parser):
        """
        :param parser: config parser pre-loaded with ``service.ini``
        :type parser: ConfigParser
        """
        for section in parser.sections():
            self._service_configurations[section] = (
                ServiceConfigurationProvider(
                    service=section,
                    form_file=parser.get(section, 'form'),
                    execution_config_file=parser.get(section, 'config')
                )
            )


class ServiceConfigurationProvider:

    def __init__(self, service, form_file, execution_config_file):
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

        with open(execution_config_file, 'r') as f:
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
            "filename": os.path.join(_LOGS_DIR, 'scheduler.log'),
            "encoding": "utf-8"
        },
        "task_queue_file": {
            "class": "logging.FileHandler",
            "formatter": "default",
            "level": "DEBUG",
            "filename": os.path.join(_LOGS_DIR, 'queue.log'),
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
