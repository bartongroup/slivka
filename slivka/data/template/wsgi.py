import os

SETTINGS_FILE = 'settings.yml'

settings_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    SETTINGS_FILE
)
os.environ.setdefault('SLIVKA_SETTINGS', settings_path)

from slivka.server.serverapp import app

application = app
