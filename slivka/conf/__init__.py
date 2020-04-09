import os

import yaml

from slivka.utils import cached_property
from . import loaders


class SettingsProxy:
    settings_file = None

    def __init__(self):
        if 'SLIVKA_SETTINGS' in os.environ:
            settings_path = os.environ['SLIVKA_SETTINGS']
        else:
            home = os.getenv('SLIVKA_HOME', os.getcwd())
            settings_path = os.path.join(home, 'settings.yaml')
            if not os.path.isfile(settings_path):
                settings_path = os.path.join(home, 'settings.yml')
        version = yaml.safe_load(open(settings_path)).get('VERSION', '1.0')
        if version == '1.0':
            self.loader = loaders.SettingsLoaderV10()
        elif version == '1.1':
            self.loader = loaders.SettingsLoaderV11()
        else:
            raise ValueError("Invalid settings version %s" % version)

    @cached_property
    def settings(self) -> loaders.Settings:
        return self.loader()

    def __getattr__(self, item):
        val = getattr(self.settings, item)
        self.__dict__[item] = val
        return val


settings = SettingsProxy()
