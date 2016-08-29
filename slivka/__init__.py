import slivka.config

settings = None  # type: slivka.config.Settings


def setup(settings_module):
    global settings
    settings = slivka.config.Settings(settings_module)
