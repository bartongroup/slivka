import pybioas.config

settings = None  # type: pybioas.config.Settings


def setup(settings_module):
    global settings
    settings = pybioas.config.Settings(settings_module)
