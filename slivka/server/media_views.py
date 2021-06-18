import os

import flask


def serve_uploads_view(file_path):
    return flask.send_from_directory(
        directory=flask.current_app.config['uploads_dir'],
        filename=file_path
    )


def serve_results_view(job_id, file_path):
    return flask.send_from_directory(
        directory=flask.current_app.config['jobs_dir'],
        filename=os.path.join(job_id, file_path)
    )
