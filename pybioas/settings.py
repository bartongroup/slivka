import os.path


BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
try: os.mkdir(UPLOAD_DIR)
except FileExistsError: pass

WORK_DIR = os.path.join(BASE_DIR, "workDirs")
try: os.mkdir(WORK_DIR)
except FileExistsError: pass

SECRET_KEY = "ftjMYc2DkqK8ljq9y7I8QhtyNac4ZYPg"

SERVICE_CONFIG = os.path.join(BASE_DIR, "data", "conf", "services.ini")
SERVICES = "Dummy", "PyDummy"
