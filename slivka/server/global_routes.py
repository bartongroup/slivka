import flask

import slivka

bp = flask.Blueprint('root', __name__)


@bp.route(slivka.settings.UPLOADS_URL_PATH + '/<path:location>',
          endpoint='uploads',
          methods=['GET'])
def serve_uploads_file(location):
    return flask.send_from_directory(
        directory=slivka.settings.UPLOADS_DIR,
        filename=location
    )


@bp.route(slivka.settings.JOBS_URL_PATH + '/<path:location>',
          endpoint='outputs',
          methods=['GET'])
def serve_tasks_file(location):
    return flask.send_from_directory(
        directory=slivka.settings.TASKS_DIR,
        filename=location
    )
