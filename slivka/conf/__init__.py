import os
import sys
import types

import yaml

from . import loaders
from slivka.utils import cached_property


def _load():
    home = os.getenv("SLIVKA_HOME", os.getcwd())
    files = ['settings.yaml', 'settings.yml', 'config.yaml', 'config.yml']
    files = (os.path.join(home, fn) for fn in files)
    try:
        file = next(filter(os.path.isfile, files))
        return _load_file(file)
    except StopIteration:
        raise loaders.ImproperlyConfigured(
            'Settings file not found in %s. Check if SLIVKA_HOME environment '
            'variable is set correctly and the directory contains '
            'settings.yaml or config.yaml.' % home
        )


def _load_file(fp):
    if isinstance(fp, str):
        fp = open(fp)
    return _load_dict(yaml.safe_load(fp))


def _load_dict(config):
    conf = loaders.load_settings_0_3(config)
    os.makedirs(conf.directory.jobs, exist_ok=True)
    os.makedirs(conf.directory.logs, exist_ok=True)
    os.makedirs(conf.directory.uploads, exist_ok=True)
    return conf


class _ConfModule(types.ModuleType):
    def __init__(self):
        super().__init__(__name__)
        self.__path__ = __path__
        self.__file__ = __file__
        self.__loader__ = __loader__
        self.loaders = loaders

    @cached_property
    def settings(self):
        return _load()

    def load_file(self, fp):
        self.settings = _load_file(fp)

    def load_dict(self, config):
        self.settings = _load_dict(config)


settings = ... # type: loaders.SlivkaSettings

sys.modules[__name__] = _ConfModule()
