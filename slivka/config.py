import configparser
import os
import types


# todo: Settings should be a singleton created once on startup.
class Settings:
    # noinspection PyUnresolvedReferences
    """Container class for all project settings.

    The settings object is initialized by the ``slivka.setup`` function every
    time Slivka is started and stored in a global variable ``slivka.settings``.
    It contains all configuration information used during runtime and is
    globally accessible to every module.

    Settings object is initialized with either a local settings module file or
    a dictionary from which all uppercase names are extracted and their values
    are stored as object attributes.

    Object attributes might change depending on the values stored in the
    settings file. However, a set of fields is pre-defined and is always
    accessible, either overridden by custom configuration or default.

    :var BASE_DIR: root directory of the project (default: cwd)
    :var LOG_DIR: log files directory (default: ``BASE_DIR/logs``)
    :var MEDIA_DIR: media files directory (default: ``BASE_DIR/media``)
    :var SECRET_KEY: key used for id signatures
    :var WORK_DIR: working directory for local jobs
    :var SERVICE_INI: location of services configuration file
    :var CONFIG: parsed services configuration file
    :var QUEUE_HOST: hostname of queue process
    :var QUEUE_PORT: task queue listening port
    :var SERVER_HOST: http server hostname
    :var SERVER_PORT: http server listening port
    :var DEBUG: enable debugging
    """
    BASE_DIR = '.'
    LOG_DIR = "logs"
    MEDIA_DIR = "media"
    SECRET_KEY = ""
    WORK_DIR = "work_dir"
    SERVICE_INI = "services.ini"
    CONFIG = None
    QUEUE_HOST = 'localhost'
    QUEUE_PORT = 3397
    SERVER_HOST = 'localhost'
    SERVER_PORT = 8000
    DEBUG = True

    def __init__(self, settings=None):
        """Initialize settings object with module of dictionary

        Creates a settings object which will validate and store the parameters
        passed to it as a module file or a dictionary.

        :param settings: settings module of dictionary
        :type settings: types.ModuleType | dict
        """
        if isinstance(settings, types.ModuleType):
            self._load_module(settings)
        elif isinstance(settings, dict):
            self._load_dict(settings)
        elif settings is None:
            pass
        self.CONFIG = configparser.ConfigParser()
        self._parse()

    def _load_dict(self, settings_dict):
        """Load all uppercase dictionary keys to object attributes."""
        for field, val in settings_dict.items():
            if field.isupper():
                setattr(self, field, val)

    def _load_module(self, settings_module):
        """Load all uppercase module variables to object attributes."""
        for field in dir(settings_module):
            if field.isupper():
                setattr(self, field, getattr(settings_module, field))

        if not os.path.isabs(self.BASE_DIR):
            file_location = os.path.abspath(settings_module.__file__)
            self.BASE_DIR = os.path.join(file_location, self.BASE_DIR)

    def _parse(self):
        """Parse all paths to be absolute and initialize configurations

        All specified paths are normalised and, in case of relative paths,
        appended to the ``BASE_DIR``.
        Services configuration is read from the ``SERVICE_INI`` file and
        loaded to the ConfigParser.
        Logger configuration is loaded from the template and path fields are
        populated with the ``LOG_DIR`` location.
        """
        self.BASE_DIR = os.path.abspath(self.BASE_DIR)

        self.LOG_DIR = self._normalize_path(self.LOG_DIR)
        os.makedirs(self.LOG_DIR, exist_ok=True)

        self.MEDIA_DIR = self._normalize_path(self.MEDIA_DIR)
        os.makedirs(self.MEDIA_DIR, exist_ok=True)

        self.WORK_DIR = self._normalize_path(self.WORK_DIR)
        os.makedirs(self.WORK_DIR, exist_ok=True)

        self.SERVICE_INI = self._normalize_path(self.SERVICE_INI)
        if not os.path.isfile(self.SERVICE_INI):
            raise ImproperlyConfigured(
                "{} is not a file.".format(self.SERVICE_INI)
            )
        self.CONFIG.read(self.SERVICE_INI)
        self.CONFIG.optionxform = lambda option: option

        if not isinstance(self.SERVER_PORT, int):
            raise ImproperlyConfigured("SERVER_PORT must be an integer")
        if not isinstance(self.QUEUE_PORT, int):
            raise ImproperlyConfigured("QUEUE_PORT must be an integer")

        self.LOGGER_CONF = _LOGGER_CONF_TEMPLATE.copy()
        self.LOGGER_CONF['handlers']['scheduler_file']['filename'] = \
            os.path.join(self.LOG_DIR, 'Scheduler.log')
        self.LOGGER_CONF['handlers']['task_queue_file']['filename'] = \
            os.path.join(self.LOG_DIR, 'TaskQueue.log')

    def _normalize_path(self, path):
        """Normalize path and make absolute.

        Normalizes the path and, if not absolute, appends it to the
        ``BASE_DIR`` path.

        :param path: initial path
        :type path: str
        :return: normalized path
        :rtype: str
        """
        if not os.path.isabs(path):
            path = os.path.join(self.BASE_DIR, path)
        return os.path.normpath(path)

    # noinspection PyPep8Naming
    @property
    def SERVICES(self):
        """List of services form the services configuration file"""
        return list(self.CONFIG.sections())


class ImproperlyConfigured(Exception):
    """Exception raised when configuration values are invalid."""


_LOGGER_CONF_TEMPLATE = {
    "version": 1,
    "root": {
        "level": "INFO",
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
            "filename": None,  # filename is completed in runtime
            "encoding": "utf-8"
        },
        "task_queue_file": {
            "class": "logging.FileHandler",
            "formatter": "default",
            "level": "DEBUG",
            "filename": None,  # filename is completed in runtime
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
