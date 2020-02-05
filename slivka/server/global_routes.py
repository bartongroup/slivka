import flask

import slivka

bp = flask.Blueprint('root', __name__)


@bp.route(slivka.settings.uploads_url_path + '/<path:location>',
          endpoint='uploads',
          methods=['GET'])
def serve_uploads_file(location):
    return flask.send_from_directory(
        directory=slivka.settings.uploads_dir,
        filename=location
    )


@bp.route(slivka.settings.jobs_url_path + '/<path:location>',
          endpoint='outputs',
          methods=['GET'])
def serve_tasks_file(location):
    return flask.send_from_directory(
        directory=slivka.settings.jobs_dir,
        filename=location
    )
