import flask
from werkzeug.wsgi import peek_path_info, pop_path_info

from slivka.server.forms import FormLoader

try:
    import simplejson as json
except ImportError:
    import json

import slivka


class PrefixMiddleware:
    def __init__(self, wsgi_app, prefix=''):
        self.app = wsgi_app
        self.prefix = prefix.strip('/')

    def __call__(self, environ, start_response):
        if peek_path_info(environ) == self.prefix:
            pop_path_info(environ)
        return self.app(environ, start_response)


def init():
    """Initializes server configuration from settings."""
    FormLoader().read_settings()


def create_app(prefix=None):
    app = flask.Flask('slivka', static_url_path='')
    app.config.update(
        UPLOADS_DIR=slivka.settings.uploads_dir
    )
    from . import api_routes
    from . import global_routes
    app.register_blueprint(api_routes.bp, url_prefix='/api')
    app.register_blueprint(api_routes.bp)
    app.register_blueprint(global_routes.bp)
    prefix = prefix or slivka.settings.url_prefix
    if prefix is not None:
        app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix)
    return app


# noinspection PyPep8Naming
def JsonResponse(content, status=200, **kwargs):
    """Create JSON response form a dictionary.

    This is a wrapper function around a ``flask.Response`` object which
    automatically serializes ``content`` as a JSON object and sets response
    mimetype to *application/json*.

    :param content: dictionary with response content
    :param status: HTTP response status code
    :param kwargs: additional arguments passed to the Response object
    :return: JSON response object
    """
    return flask.Response(
        response=json.dumps(content, indent=2),
        status=status,
        mimetype='application/json',
        **kwargs
    )
