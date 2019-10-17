import os

import slivka.conf.logging
import slivka.server

SETTINGS_FILE = 'settings.yml'

settings_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    SETTINGS_FILE
)
os.environ.setdefault('SLIVKA_SETTINGS', settings_path)
slivka.conf.logging.configure_logging()

application = app = slivka.server.create_app()
