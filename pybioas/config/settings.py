import os

from .exceptions import ImproperlyConfigured


class Settings:

    BASE_DIR = os.curdir
    SECRET_KEY = ""
    UPLOAD_DIR = "uploads"
    WORK_DIR = "work_dir"
    SERVICE_CONFIG = os.path.join("config", "services.ini")
    SERVICES = ()

    def __init__(self, settings_module):
        """
        :param settings_module: module where constants are loaded from
        """
        # load settings from the `settings_module`
        for field in dir(settings_module):
            if field.isupper():
                setattr(self, field, getattr(settings_module, field))

        if not os.path.isabs(self.BASE_DIR):
            self.BASE_DIR = os.path.join(
                settings_module.__file__, self.BASE_DIR
            )

        if not self.SECRET_KEY:
            raise ImproperlyConfigured("Field SECRET_KEY is not set.")

        if not os.path.isabs(self.UPLOAD_DIR):
            self.UPLOAD_DIR = os.path.join(self.BASE_DIR, self.UPLOAD_DIR)
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)

        if not os.path.isabs(self.WORK_DIR):
            self.WORK_DIR = os.path.join(self.BASE_DIR, self.WORK_DIR)
        os.makedirs(self.WORK_DIR, exist_ok=True)

        if not os.path.isabs(self.SERVICE_CONFIG):
            self.SERVICE_CONFIG = os.path.join(
                self.BASE_DIR, self.SERVICE_CONFIG
            )
        if not os.path.isfile(self.SERVICE_CONFIG):
            raise ImproperlyConfigured(
                "{} is not a file.".format(self.SERVICE_CONFIG)
            )

        if not isinstance(self.SERVICES, (tuple, list)):
            raise ImproperlyConfigured(
                "SERVICES must be a list or tuple of service names"
            )
