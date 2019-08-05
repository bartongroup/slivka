"""Provides wsgi application and routes for each possible request

This module initializes a global instance of Flask application and sets it's
configuration based on the provided config file.
It also contains and binds all url routes to functions taking a request and
producing a json response.

Flask application ``app`` contained in this module can be used as a
standalone HTTP debugging server or can be passed to the dedicated wsgi
server e.g. Apache with mod_wsgi, uWSGI or Gunicorn.
"""

import os.path
from tempfile import mkstemp

import flask
import pkg_resources
import slivka
import sqlalchemy.orm.exc
from flask import json, request, abort
from slivka.db import Session, models, start_session
from slivka.server.file_validators import validate_file_content

from .forms import FormLoader

app = flask.Flask('slivka', root_path=slivka.settings.BASE_DIR)
"""Flask object implementing WSGI application."""
app.config.update(
    UPLOADS_DIR=slivka.settings.UPLOADS_DIR
)


@app.route('/version', methods=['GET'])
def get_version():
    return JsonResponse({
        'statuscode': 200,
        'version': slivka.__version__
    })


@app.route('/services', methods=['GET'])
def get_services():
    """Return the list of services. ``GET /services``

    :return: JSON response with list of service names
    """
    return JsonResponse({
        'statuscode': 200,
        'services': [
            {
                'name': service,
                'URI': flask.url_for('get_service_form', service=service)
            }
            for service in slivka.settings.services
        ]
    })


@app.route('/services/<service>', methods=['GET'])
def get_service_form(service):
    """Gets service request form. ``GET /service/{service}/form``

    :param service: service name
    :return: JSON response with service form
    """
    if service not in slivka.settings.services:
        raise abort(404)
    form_cls = FormLoader.instance[service]
    form = form_cls()
    response = {
        'statuscode': 200,
        'name': service,
        'URI': flask.url_for('post_service_form', service=service),
        'fields': [field.__json__() for field in form]
    }
    return JsonResponse(response, status=200)


@app.route('/services/<service>', methods=['POST'])
def post_service_form(service):
    """Send form data and starts new task. ``POST /service/{service}/form``

    :param service: service name
    :return: JSON response with submitted task id
    """
    if service not in slivka.settings.services:
        raise abort(404)
    form_cls = FormLoader.instance[service]
    form = form_cls(request.form, request.files)
    if form.is_valid():
        with start_session() as session:
            job_request = form.save(session)
            session.commit()
            return JsonResponse({
                'statuscode': 202,
                'uuid': job_request.uuid,
                'URI': flask.url_for('get_task_status', task_uuid=job_request.uuid)
            }, status=202)
    else:
        return JsonResponse({
            'statuscode': 420,
            'error': 'Invalid data',
            'errors': [
                {'field': name,
                 'message': error.message,
                 'errorCode': error.code}
                for name, error in form.errors.items()
            ]
        }, status=420)


@app.route('/files', methods=['POST'])
def file_upload():
    """Upload the file to the server. ``POST /files``

    :return: JSON containing internal metadata of the uploaded file
    """
    try:
        file = request.files['file']
    except KeyError:
        raise abort(400)
    if not validate_file_content(file, file.mimetype):
        raise abort(415)
    file.seek(0)
    (fd, path) = mkstemp('', '', dir=app.config['UPLOADS_DIR'], text=False)
    fname = os.path.basename(path)
    with os.fdopen(fd, 'wb') as fp:
        file.save(fp)
    file_record = models.File(
        title=file.filename,
        mimetype=file.mimetype,
        path=path,
        url_path=flask.url_for('uploads', filename=fname)
    )
    with start_session() as session:
        session.expire_on_commit = False
        session.add(file_record)
        session.commit()
    return JsonResponse({
        'statuscode': 201,
        'uuid': file_record.uuid,
        'title': file.filename,
        'mimetype': file.mimetype,
        'URI': flask.url_for('get_file_metadata', file_uuid=file_record.uuid),
        'contentURI': file_record.url_path
    }, status=201)


@app.route('/files/<file_uuid>', methods=['GET'])
def get_file_metadata(file_uuid):
    """Get file metadata. ``GET /file/{file_uuid}``

    :param file_uuid: file identifier
    :return: JSON containing internal metadata of the file
    """
    session = Session()
    try:
        file = (session.query(models.File)
                .filter(models.File.uuid == file_uuid)
                .one())
    except sqlalchemy.orm.exc.NoResultFound:
        raise abort(404)
    finally:
        session.close()
    return JsonResponse({
        'statuscode': 200,
        'uuid': file.uuid,
        'title': file.title,
        'mimetype': file.mimetype,
        'URI': flask.url_for('get_file_metadata', file_uuid=file_uuid),
        'contentURI': file.url_path
    }, status=200)


@app.route(slivka.settings.UPLOADS_URL_PATH + '/<path:filename>',
           endpoint='uploads',
           methods=['GET'])
def serve_uploads_file(filename):
    return flask.send_from_directory(
        directory=slivka.settings.UPLOADS_DIR,
        filename=filename
    )


@app.route(slivka.settings.TASKS_URL_PATH + '/<path:filename>',
           endpoint='tasks',
           methods=['GET'])
def serve_tasks_file(filename):
    return flask.send_from_directory(
        directory=slivka.settings.TASKS_DIR,
        filename=filename
    )


@app.route('/tasks/<task_uuid>', methods=['GET'])
def get_task_status(task_uuid):
    """Get the status of the task. ``GET /task/{task_uuid}/status``

    :param task_uuid: task identifier
    :return: JSON response with current job completion status
    """
    with start_session() as session:
        try:
            job_request = (session.query(models.Request)
                           .filter_by(uuid=task_uuid)
                           .one())
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)
        return JsonResponse({
            'statuscode': 200,
            'status': job_request.status_string,
            'ready': job_request.is_finished(),
            'filesURI': flask.url_for('get_task_files', task_uuid=task_uuid)
        })


@app.route('/tasks/<task_uuid>', methods=['DELETE'])
def cancel_task(task_uuid):
    raise NotImplementedError


@app.route('/tasks/<task_uuid>/files', methods=['GET'])
def get_task_files(task_uuid):
    """Get the list of output files. ``GET /task/{task_id}/files``

    :param task_uuid: task identifier
    :return: JSON response with list of files produced by the task.
    """
    with start_session() as session:
        try:
            req = (session.query(models.Request)
                   .filter_by(uuid=task_uuid)
                   .one())
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)

        files = (session.query(models.File)
                 .filter_by(request=req)
                 .all())
        return JsonResponse({
            'statuscode': 200,
            'files': [
                {'uuid': file.uuid,
                 'title': file.title,
                 'mimetype': file.mimetype,
                 'URI': flask.url_for('get_file_metadata', file_uuid=file.uuid),
                 'contentURI': file.url_path}
                for file in files
            ]
        }, status=200)


@app.route('/webapp/<service>', methods=['GET', 'POST'])
def webapp_form(service):
    Form = FormLoader.instance[service]
    if request.method == 'GET':
        form = Form()
        return flask.render_template('form.jinja2', form=form)
    elif request.method == 'POST':
        form = Form(data=request.form, files=request.files)
        if form.is_valid():
            with start_session(expire_on_commit=False) as session:
                job_request = form.save(session)
                session.commit()
            url =flask.url_for('get_task_status', task_uuid=job_request.uuid)
            print(url)
            return flask.redirect(url)
        else:
            return flask.render_template('form.jinja2', form=form)


@app.route('/api/')
def api_index():
    path = pkg_resources.resource_filename('slivka', 'data/swagger-ui-dist/')
    return flask.send_from_directory(path, 'index.html')


@app.route('/api/openapi.yaml')
def serve_openapi_yaml():
    stream = pkg_resources.resource_stream(
        'slivka', 'data/openapi-docs/openapi.yaml'
    )
    return flask.send_file(stream, 'application/yaml', as_attachment=False)


@app.route('/api/<path:filename>')
def serve_api_static(filename=None):
    path = pkg_resources.resource_filename('slivka', 'data/swagger-ui-dist/')
    return flask.send_from_directory(path, filename)


@app.route('/echo', methods=['GET', 'POST', 'PUT', 'DELETE'])
def echo():
    """Return request method and POST and GET arguments.

    :return: JSON response with basic request information.
    """
    return JsonResponse(
        dict(
            method=request.method,
            args=request.args,
            form=request.form
        ),
        status=200
    )


def error_response(status, message):
    return JsonResponse({'statuscode': status, 'error': message}, status)


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


app.register_error_handler(
    400, lambda e: error_response(400, 'Bad request')
)
app.register_error_handler(
    401, lambda e: error_response(401, 'Unauthorized')
)
app.register_error_handler(
    404, lambda e: error_response(404, 'Not found')
)
app.register_error_handler(
    405, lambda e: error_response(405, 'Method not allowed')
)
app.register_error_handler(
    415, lambda e: error_response(415, 'Unsupported media type')
)
app.register_error_handler(
    500, lambda e: error_response(500, 'Internal server error')
)
app.register_error_handler(
    503, lambda e: error_response(503, 'Service unavailable')
)
