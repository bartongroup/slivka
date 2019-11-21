import flask
from werkzeug.wsgi import peek_path_info, pop_path_info

try:
    import simplejson as json
except ImportError:
    import json

import slivka


_app = None


class PrefixMiddleware:
    def __init__(self, wsgi_app, prefix=''):
        self.app = wsgi_app
        self.prefix = prefix.strip('/')

    def __call__(self, environ, start_response):
        if peek_path_info(environ) == self.prefix:
            pop_path_info(environ)
        return self.app(environ, start_response)


def create_app(prefix=None):
    global _app
    if _app is not None:
        raise RuntimeError("Flask application already exists")
    _app = flask.Flask('slivka')
    _app.config.update(
        UPLOADS_DIR=slivka.settings.UPLOADS_DIR
    )
    from . import api_routes
    from . import global_routes
    _app.register_blueprint(api_routes.bp, url_prefix='/api')
    _app.register_blueprint(api_routes.bp)
    _app.register_blueprint(global_routes.bp)
    prefix = prefix or slivka.settings.URL_PREFIX
    if prefix is not None:
        _app.wsgi_app = PrefixMiddleware(_app.wsgi_app, prefix)
    return _app


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
