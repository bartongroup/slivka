import contextlib

from slivka.utils import cached_property
from . import loaders


class SettingsProxy:
    settings_file = None

    @cached_property
    def settings(self) -> loaders.Settings:
        # Try loading with a primary loader. If that fails, then try
        # secondary loaders. If they fail as well, re-raise the
        # exception from the primary loader.
        try:
            loader = loaders.SettingsLoaderV11()
            return loader()
        except loaders.ImproperlyConfigured as e:
            with contextlib.suppress(loaders.ImproperlyConfigured):
                loader = loaders.SettingsLoaderV10()
                return loader()
            raise

    def __getattr__(self, item):
        val = getattr(self.settings, item)
        self.__dict__[item] = val
        return val


settings = SettingsProxy()
