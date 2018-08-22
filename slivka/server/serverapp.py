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
import tempfile

import flask
import itsdangerous
import pkg_resources
import sqlalchemy.orm.exc
import werkzeug.exceptions
import werkzeug.utils
from flask import Flask, Response, json, request, abort

import slivka
from slivka.db import Session, models, start_session
from slivka.server.forms import FormFactory
from slivka.server.file_validators import validate_file_type
from slivka.utils import snake_to_camel

app = Flask('slivka', root_path=slivka.settings.BASE_DIR)
"""Flask object implementing WSGI application."""
app.config.update(
    DEBUG=slivka.settings.DEBUG,
    MEDIA_DIR=slivka.settings.MEDIA_DIR,
    SECRET_KEY=slivka.settings.SECRET_KEY
)

signer = itsdangerous.Signer(slivka.settings.SECRET_KEY)


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
                'submitURI': '/service/%s/form' % service
            }
            for service in slivka.settings.services
        ]
    })


@app.route('/service/<service>/form', methods=['GET'])
def get_service_form(service):
    """Gets service request form. ``GET /service/{service}/form``

    :param service: service name
    :return: JSON response with service form
    """
    if service not in slivka.settings.services:
        raise abort(404)
    form_cls = FormFactory().get_form_class(service)
    form = form_cls()
    response = {
        'statuscode': 200,
        'form': form_cls.__name__,
        'service': service,
        'submitURI': '/service/%s/form' % service,
        'fields': [
            {
                'name': field.name,
                'type': field.type,
                'label': field.label,
                'description': field.description,
                'required': field.required,
                'default': field.default,
                'constraints': [
                    {
                        'name': snake_to_camel(constraint['name']),
                        'value': constraint['value']
                    }
                    for constraint in field.constraints
                ]
            }
            for field in form.fields
        ]
    }
    return JsonResponse(response, status=200)


@app.route('/service/<service>/form', methods=['POST'])
def post_service_form(service):
    """Send form data and starts new task. ``POST /service/{service}/form``

    :param service: service name
    :return: JSON response with submitted task id
    """
    if service not in slivka.settings.services:
        raise abort(404)
    form_cls = FormFactory().get_form_class(service)
    form = form_cls(request.form)
    if form.is_valid():
        with start_session() as session:
            job_request = form.save(session)
            session.commit()
            response = JsonResponse({
                'statuscode': 202,
                'taskId': job_request.uuid,
                'checkStatusURI': '/task/%s/status' % job_request.uuid
            }, status=202)
    else:
        response = JsonResponse({
            'errors': [{
                'statuscode': 420,
                'field': name,
                'errorCode': error.code,
                'message': error.reason
            } for name, error in form.errors.items()]
        }, status=420)
    return response


@app.route('/file', methods=['POST'])
def file_upload():
    """Upload the file to the server. ``POST /file``

    :return: JSON containing internal metadata of the uploaded file
    """
    try:
        file = request.files['file']
    except KeyError:
        raise abort(400)
    if not validate_file_type(file._file, file.mimetype):
        raise abort(415)
    file.stream.seek(0)
    filename = werkzeug.utils.secure_filename(file.filename)
    with tempfile.NamedTemporaryFile(
            dir=app.config['MEDIA_DIR'], delete=False) as tf:
        file.save(tf)
    file_record = models.File(
        title=filename,
        mimetype=file.mimetype,
        path=tf.name
    )
    with start_session() as session:
        session.add(file_record)
        session.commit()
        file_id = file_record.id
    return JsonResponse({
        'statuscode': 201,
        'id': file_id,
        'signedId':
            signer.sign(itsdangerous.want_bytes(file_id)).decode('utf-8'),
        'title': filename,
        'mimetype': file.mimetype,
        'downloadURI': '/file/%s/download' % file_id
    }, status=201)


@app.route('/file/<file_id>', methods=['GET'])
def get_file_meta(file_id):
    """Get file metadata. ``GET /file/{file_id}``

    :param file_id: file identifier
    :return: JSON containing internal metadata of the file
    """
    session = Session()
    try:
        file = (session.query(models.File)
                .filter(models.File.id == file_id)
                .one())
    except sqlalchemy.orm.exc.NoResultFound:
        raise abort(404)
    finally:
        session.close()
    return JsonResponse({
        'statuscode': 200,
        'id': file.id,
        'title': file.title,
        'mimetype': file.mimetype,
        'downloadURI': '/file/%s/download' % file.id
    }, status=200)


@app.route('/file/<file_id>/download', methods=['GET'])
def file_download(file_id):
    """Download file contents. ``GET /file/{file_id}/download``

    :param file_id: file identifier
    :return: requested file contents
    """
    with start_session() as session:
        try:
            file = (session.query(models.File)
                    .filter(models.File.id == file_id)
                    .one())
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)
        return flask.send_from_directory(
            directory=os.path.dirname(file.path),
            filename=os.path.basename(file.path),
            attachment_filename=file.title or os.path.basename(file.path),
            mimetype=file.mimetype
        )


@app.route('/file/<signed_file_id>', methods=['PUT'])
def set_file_meta(signed_file_id):
    """Update file metadata. ``PUT /file/{signed_file_id}``

    :param signed_file_id: signed file identifier
    :return: JSON containing new metadata of the file
    """
    try:
        file_id = signer.unsign(signed_file_id).decode('utf-8')
    except itsdangerous.BadSignature:
        raise abort(401)
    with start_session() as session:
        try:
            file = (session.query(models.File).
                    filter(models.File.id == file_id).
                    one())
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)
        new_title = request.form.get('title')
        if new_title is not None:
            file.title = new_title
        session.commit()
        return JsonResponse({
            'statuscode': 200,
            'id': file.id,
            'signedId': signed_file_id,
            'title': file.title,
            'mimetype': file.mimetype,
            'downloadURI': '/file/%s/download' % file.id
        }, status=200)


@app.route('/file/<signed_file_id>', methods=['DELETE'])
def delete_file(signed_file_id):
    """Delete file from the filesystem. ``DELETE /file/{signed_file_id}``

    :param signed_file_id: signed file identifier
    :return: Http response with status code
    """
    try:
        file_id = signer.unsign(signed_file_id).decode('utf-8')
    except itsdangerous.BadSignature:
        raise abort(401)
    path = None
    with start_session() as session:
        try:
            file = (session.query(models.File).
                    filter(models.File.id == file_id).
                    one())
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)
        path = file.path
        session.delete(file)
        session.commit()
    try:
        os.remove(path)
    except FileNotFoundError:
        raise abort(404)
    return JsonResponse({'statuscode': 200}, status=200)


@app.route('/task/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """Get the status of the task. ``GET /task/{task_id}/status``

    :param task_id: task identifier
    :return: JSON response with current job completion status
    """
    with start_session() as session:
        try:
            job_request = (session.query(models.Request)
                           .filter_by(uuid=task_id)
                           .one())
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)
        return JsonResponse({
            'statuscode': 200,
            'execution': job_request.status_string,
            'ready': job_request.is_finished(),
            'resultURI': '/task/%s/result' % task_id
        })


@app.route('/task/<task_id>/result', methods=['GET'])
def get_task_result(task_id):
    """Get the list of output files. ``GET /task/{task_id}/files``

    :param task_id: task identifier
    :return: JSON response with list of files produced by the task.
    """
    with start_session() as session:
        try:
            req = (session.query(models.Request)
                   .filter_by(uuid=task_id)
                   .one())
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)

        files = (session.query(models.File)
                 .filter_by(request=req)
                 .all())
        return JsonResponse({
            'statuscode': 200,
            'files': [
                {
                    'id': file.id,
                    'title': file.title,
                    'mimetype': file.mimetype,
                    'downloadURI': '/file/%s/download' % file.id
                }
                for file in files
            ]
        }, status=200)


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
    return Response(
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
