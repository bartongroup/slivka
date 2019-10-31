import json
import logging.config
import os.path
import sys
import warnings

import jsonschema
import pkg_resources
import yaml

from slivka.utils import SafeTranscludingOrderedYamlLoader


class ImproperlyConfigured(Exception):
    pass


class LazySettingsProxy:

    def __init__(self):
        self._settings = None

    def __getattr__(self, item):
        if self._settings is None:
            self._setup()
        val = getattr(self._settings, item)
        self.__dict__[item] = val
        return val

    def _setup(self):
        settings_file = os.environ.get("SLIVKA_SETTINGS")
        if not settings_file:
            raise ImproperlyConfigured(
                'Settings are not configured. You must set the environment '
                'variable SLIVKA_SETTINGS.'
            )
        with open(settings_file) as f:
            self._settings = Settings(yaml.safe_load(f))

    def configure(self, **options):
        if self._settings is not None:
            warnings.warn("Settings already configured")
        self._settings = type('Settings', (), {})()
        for name, value in options.items():
            setattr(self._settings, name, value)


class Settings:

    def __init__(self, json_data):
        for name, value in json_data.items():
            if name.isupper():
                setattr(self, name, value)
        self._service_configs = {}

        # check if all required fields are present
        required_options = ['BASE_DIR', 'UPLOADS_DIR', 'JOBS_DIR', 'SERVICES',
                            'UPLOADS_URL_PATH', 'JOBS_URL_PATH',
                            'ACCEPTED_MEDIA_TYPES',
                            'SERVER_HOST', 'SERVER_PORT', 'SLIVKA_QUEUE_ADDR',
                            'MONGODB_ADDR']
        for option in required_options:
            if not hasattr(self, option):
                raise ImproperlyConfigured(
                    '%s is missing from settings' % option
                )

        # join paths with BASE_DIR
        self.BASE_DIR = os.path.abspath(self.BASE_DIR)
        self.UPLOADS_DIR = norm_join_path(self.BASE_DIR, self.UPLOADS_DIR)
        self.JOBS_DIR = norm_join_path(self.BASE_DIR, self.JOBS_DIR)
        for path in [self.UPLOADS_DIR, self.JOBS_DIR]:
            os.makedirs(path, exist_ok=True)
        self.SERVICES = norm_join_path(self.BASE_DIR, self.SERVICES)

        # load services configurations
        with open(self.SERVICES) as f:
            services_config = yaml.safe_load(f)
        for service, section in services_config.items():
            self._service_configs[service] = ServiceConfig(
                name=service,
                label=section['label'],
                form_file=os.path.join(self.BASE_DIR, section['form']),
                command_file=os.path.join(self.BASE_DIR, section['command']),
                presets_file=os.path.join(self.BASE_DIR, section['presets']) if 'presets' in section else None,
                classifiers=section.get('classifiers', [])
            )

    @property
    def TASKS_DIR(self):
        warnings.warn('TASKS_DIR is deprecated', DeprecationWarning)
        return self.JOBS_DIR

    @property
    def SERVICES_INI(self):
        warnings.warn('SERVICES_INI is deprecated', DeprecationWarning)
        return self.SERVICES

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


form_def_schema = json.loads(
    pkg_resources.resource_string(
        "slivka.conf", "formDefSchema.json"
    ).decode()
)
jsonschema.Draft4Validator.check_schema(form_def_schema)
form_def_validator = jsonschema.Draft4Validator(form_def_schema)

command_def_schema = json.loads(
    pkg_resources.resource_string(
        "slivka.conf", "commandDefSchema.json"
    ).decode()
)
jsonschema.Draft4Validator.check_schema(command_def_schema)
command_def_validator = jsonschema.Draft4Validator(command_def_schema)

presets_schema = json.loads(
    pkg_resources.resource_string(
        "slivka.conf", "presetsSchema.json"
    ).decode()
)
jsonschema.Draft4Validator.check_schema(presets_schema)
presets_validator = jsonschema.Draft4Validator(presets_schema)


class ServiceConfig:

    def __init__(self, name, label, form_file, command_file, presets_file=None, classifiers=()):
        self.name = name
        self.label = label
        self.classifiers = classifiers

        with open(form_file, 'r') as f:
            form = yaml.load(f, SafeTranscludingOrderedYamlLoader)
        try:
            form_def_validator.validate(form)
            self._form = form
        except jsonschema.exceptions.ValidationError:
            logging.exception(
                'Error validating form definition file %s', form_file
            )
            sys.exit(1)

        with open(command_file, 'r') as f:
            config = yaml.load(f, SafeTranscludingOrderedYamlLoader)
        try:
            command_def_validator.validate(config)
            self._execution_config = config
        except jsonschema.exceptions.ValidationError:
            logging.exception(
                'Error validating configuration file %s', command_file
            )
            sys.exit(1)

        if presets_file:
            with open(presets_file) as f:
                presets_conf = yaml.load(f, SafeTranscludingOrderedYamlLoader)
            try:
                presets_validator.validate(presets_conf)
                presets = presets_conf['presets']
            except jsonschema.exceptions.ValidationError:
                logging.exception(
                    'Error validating presets file %s', presets_file
                )
                sys.exit(1)
        else:
            presets = []
        self.presets = {preset['id']: preset for preset in presets}

    @property
    def service(self):
        return self.name

    @property
    def form(self):
        return self._form

    @property
    def command_def(self):
        return self._execution_config

    @property
    def execution_config(self):
        warnings.warn('execution_config is deprecated, use command_def',
                      DeprecationWarning)
        return self.command_def

    def __repr__(self):
        return '<%s ConfigurationProvider>' % self.name
