import os
import types


class Settings:

    BASE_DIR = os.curdir
    LOG_DIR = None
    SECRET_KEY = ""
    MEDIA_DIR = "media"
    WORK_DIR = "work_dir"
    SERVICE_INI = os.path.join("config", "services.ini")
    SERVICES = ()
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

        if not os.path.isabs(self.MEDIA_DIR):
            self.MEDIA_DIR = os.path.join(self.BASE_DIR, self.MEDIA_DIR)
        self.MEDIA_DIR = os.path.normpath(self.MEDIA_DIR)
        os.makedirs(self.MEDIA_DIR, exist_ok=True)

        if not os.path.isabs(self.WORK_DIR):
            self.WORK_DIR = os.path.join(self.BASE_DIR, self.WORK_DIR)
        self.WORK_DIR = os.path.normpath(self.WORK_DIR)
        os.makedirs(self.WORK_DIR, exist_ok=True)

        if not os.path.isabs(self.SERVICE_INI):
            self.SERVICE_INI = os.path.join(self.BASE_DIR, self.SERVICE_INI)
        self.SERVICE_INI = os.path.normpath(self.SERVICE_INI)
        if not os.path.isfile(self.SERVICE_INI):
            raise ImproperlyConfigured(
                "{} is not a file.".format(self.SERVICE_INI)
            )

        if not isinstance(self.SERVER_PORT, int):
            raise ImproperlyConfigured("SERVER_PORT must be an integer")
        if not isinstance(self.QUEUE_PORT, int):
            raise ImproperlyConfigured("QUEUE_PORT must be an integer")

        if self.LOG_DIR is None:
            self.LOG_DIR = self.BASE_DIR
        elif not os.path.isabs(self.LOG_DIR):
            self.LOG_DIR = os.path.join(self.BASE_DIR, self.LOG_DIR)

        self.LOGGER_CONF = {
            "version": 1,
            "root": {
                "level": "INFO",
                "handlers": ["console"]
            },
            "loggers": {
                "pybioas.scheduler.command": {
                    "level": "DEBUG",
                    "propagate": True,
                    "handlers": ["command_file"]
                },
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
                "command_file": {
                    "class": "logging.FileHandler",
                    "formatter": "default",
                    "level": "DEBUG",
                    "filename": os.path.join(self.LOG_DIR, 'Command.log'),
                    "encoding": "utf-8"
                },
                "scheduler_file": {
                    "class": "logging.FileHandler",
                    "formatter": "default",
                    "level": "DEBUG",
                    "filename": os.path.join(self.LOG_DIR, "Scheduler.log"),
                    "encoding": "utf-8"
                },
                "task_queue_file": {
                    "class": "logging.FileHandler",
                    "formatter": "default",
                    "level": "DEBUG",
                    "filename": os.path.join(self.LOG_DIR, "TaskQueue.log"),
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


class ImproperlyConfigured(Exception):
    pass
