import flask

try:
    import simplejson as json
except ImportError:
    import json

import slivka


_app = None


def create_app():
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
