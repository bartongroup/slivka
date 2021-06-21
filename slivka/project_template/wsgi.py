import os

import slivka.conf.logging
import slivka.server

home = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SLIVKA_HOME', home)
slivka.conf.logging.configure_logging()

application = app = slivka.server.create_app()

# If you wish to create additional web endpoints, import blueprints
# and register them with the application here.
# More info: https://flask.palletsprojects.com/en/1.1.x/blueprints/
