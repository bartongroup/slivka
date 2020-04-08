from slivka.utils import cached_property
from . import loaders


class SettingsProxy:
    settings_file = None

    def __init__(self):
        self.loader = loaders.SettingsLoaderV10()

    @cached_property
    def settings(self) -> loaders.Settings:
        return self.loader()

    def __getattr__(self, item):
        val = getattr(self.settings, item)
        self.__dict__[item] = val
        return val


settings = SettingsProxy()
