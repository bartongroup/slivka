import slivka.config

settings = None  # type: slivka.config.Settings
"""Project configuration object.

:type: :ref:slivka.config.Settings
"""


def setup(settings_module):
    """Set the ``settings`` variable to a new ``Settings`` object."""
    global settings
    settings = slivka.config.Settings(settings_module)
