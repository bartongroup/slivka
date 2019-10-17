import flask

try:
    import simplejson as json
except ImportError:
    import json

import slivka


def create_app():
    app = flask.Flask('slivka')
    app.config.update(
        UPLOADS_DIR=slivka.settings.UPLOADS_DIR
    )
    from . import serverapp
    app.register_blueprint(serverapp.bp)
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
