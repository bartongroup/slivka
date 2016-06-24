import os.path


BASE_DIR = os.path.dirname(__file__)
SERVICE_CONFIG = os.path.join(BASE_DIR, 'config', 'services.ini')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
try:
    os.mkdir(UPLOAD_DIR)
except FileExistsError:
    pass

SECRET_KEY = 'ftjMYc2DkqK8ljq9y7I8QhtyNac4ZYPg'

SERVICES = "Dummy",
