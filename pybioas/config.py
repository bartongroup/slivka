import configparser
import os
import types


class Settings:

    BASE_DIR = os.curdir
    LOG_DIR = None
    SECRET_KEY = ""
    MEDIA_DIR = "media"
    WORK_DIR = "work_dir"
    SERVICE_INI = "services.ini"
    CONFIG = None
    QUEUE_HOST = 'localhost'
    QUEUE_PORT = 3397
    SERVER_HOST = 'localhost'
    SERVER_PORT = 8000
    DEBUG = True

    def __init__(self, settings=None):
        if isinstance(settings, types.ModuleType):
            self._load_module(settings)
        elif isinstance(settings, dict):
            self._load_dict(settings)
        elif settings is None:
            pass
        self.CONFIG = configparser.ConfigParser()
        self._parse()

    def _load_dict(self, settings_dict):
        for field, val in settings_dict.items():
            if field.isupper():
                setattr(self, field, val)

    def _load_module(self, settings_module):
        """
        :param settings_module: module where constants are loaded from
        """
        # load settings from the `settings_module`
        for field in dir(settings_module):
            if field.isupper():
                setattr(self, field, getattr(settings_module, field))

        if not os.path.isabs(self.BASE_DIR):
            file_location = os.path.abspath(settings_module.__file__)
            self.BASE_DIR = os.path.join(file_location, self.BASE_DIR)

    def _parse(self):
        self.BASE_DIR = os.path.abspath(self.BASE_DIR)

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

        if self.LOG_DIR is None:
            self.LOG_DIR = self.BASE_DIR
        self.LOG_DIR = self._normalize_path(self.LOG_DIR)
        os.makedirs(self.LOG_DIR, exist_ok=True)

        self.LOGGER_CONF = _LOGGER_CONF_TEMPLATE.copy()
        self.LOGGER_CONF['handlers']['scheduler_file']['filename'] = \
            os.path.join(self.LOG_DIR, 'Scheduler.log')
        self.LOGGER_CONF['handlers']['task_queue_file']['filename'] = \
            os.path.join(self.LOG_DIR, 'TaskQueue.log')

    def _normalize_path(self, path):
        if not os.path.isabs(path):
            path = os.path.join(self.BASE_DIR, path)
        return os.path.normpath(path)

    @property
    def SERVICES(self):
        return list(self.CONFIG.sections())


class ImproperlyConfigured(Exception):
    pass


_LOGGER_CONF_TEMPLATE = {
    "version": 1,
    "root": {
        "level": "INFO",
        "handlers": ["console"]
    },
    "loggers": {
        "pybioas.scheduler.scheduler": {
            "level": "DEBUG",
            "propagate": True,
            "handlers": ["scheduler_file"]
        },
        "pybioas.scheduler.task_queue": {
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
            "filename": None,
            "encoding": "utf-8"
        },
        "task_queue_file": {
            "class": "logging.FileHandler",
            "formatter": "default",
            "level": "DEBUG",
            "filename": None,
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
