import contextlib
import os

from slivka.utils import cached_property
from . import loaders


class SettingsProxy:
    settings_file = None

    @cached_property
    def settings(self) -> loaders.Settings:
        # Try loading with a primary loader. If that fails, then try
        # secondary loaders, if they fail as well, re-raise the
        # exception from the primary loader.
        try:
            loader = loaders.SettingsLoaderV11()
            _settings = loader()
        except loaders.ImproperlyConfigured as e:
            try:
                loader = loaders.SettingsLoaderV10()
                _settings = loader()
            except loaders.ImproperlyConfigured:
                raise e from None
        os.environ['SLIVKA_HOME'] = _settings.base_dir
        return _settings

    def __getattr__(self, item):
        val = getattr(self.settings, item)
        self.__dict__[item] = val
        return val


settings = SettingsProxy()
