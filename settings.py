import os.path


BASE_DIR = os.path.dirname(__file__)
SERVICE_CONFIG = os.path.join(BASE_DIR, 'config', 'services.ini')

SERVICES = "Dummy", "Muscle"
