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
import pathlib
from collections import namedtuple
from fnmatch import fnmatch
from tempfile import mkstemp

import flask
import pkg_resources
from flask import json, request, abort

import slivka
from slivka import JobStatus
from slivka.db import mongo, documents
from .file_validators import validate_file_content
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
        request_doc = form.save(mongo.slivkadb)
        return JsonResponse({
            'statuscode': 202,
            'uuid': request_doc.uuid,
            'URI': flask.url_for('get_job_status', uuid=request_doc.uuid)
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
    filename = os.path.basename(path)
    with os.fdopen(fd, 'wb') as fp:
        file.save(fp)
    file_doc = documents.UploadedFile(
        title=file.filename,
        media_type=file.mimetype,
        path=path
    )
    file_doc.insert(mongo.slivkadb)
    return JsonResponse({
        'statuscode': 201,
        'uuid': file_doc.uuid,
        'title': file.filename,
        'mimetype': file.mimetype,
        'URI': flask.url_for('get_file_metadata', uid=file_doc.uuid),
        'contentURI': flask.url_for('uploads', location=filename)
    }, status=201)


@app.route('/files/<path:uid>', methods=['GET'])
def get_file_metadata(uid):
    """Get file metadata. ``GET /file/{file_uuid}``

    :param uid: file identifier
    :return: JSON containing internal metadata of the file
    """
    tokens = uid.split('/', 1)
    if len(tokens) == 1:
        uuid, = tokens
        file = documents.UploadedFile.find_one(
            mongo.slivkadb, uuid=uuid
        )
        if file is None:
            raise abort(404)
        return JsonResponse({
            'statuscode': 200,
            'uuid': file['uuid'],
            'title': file['title'],
            'mimetype': file['media_type'],
            'URI': flask.url_for('get_file_metadata', uid=uid),
            'contentURI': flask.url_for('uploads', location=file['basename'])
        })
    elif len(tokens) == 2:
        uuid, filename = tokens
        job = documents.JobMetadata.find_one(
            mongo.slivkadb, uuid=uuid
        )
        if job is None:
            raise abort(404)
        conf = slivka.settings.get_service_configuration(job.service)
        output = next(
            out for out in conf.execution_config['outputs'].values()
            if fnmatch(filename, out['path'])
        )
        job_location = os.path.basename(job.work_dir)
        file_location = '%s/%s' % (job_location, filename)
        return JsonResponse({
            'statuscode': 200,
            'uuid': uid,
            'title': filename,
            'mimetype': output.get('media-type'),
            'URI': flask.url_for('get_file_metadata', uid=uid),
            'contentURI': flask.url_for('outputs', location=file_location)
        })
    else:
        raise abort(404)


@app.route(slivka.settings.UPLOADS_URL_PATH + '/<path:location>',
           endpoint='uploads',
           methods=['GET'])
def serve_uploads_file(location):
    return flask.send_from_directory(
        directory=slivka.settings.UPLOADS_DIR,
        filename=location
    )


@app.route(slivka.settings.JOBS_URL_PATH + '/<path:location>',
           endpoint='outputs',
           methods=['GET'])
def serve_tasks_file(location):
    return flask.send_from_directory(
        directory=slivka.settings.TASKS_DIR,
        filename=location
    )


@app.route('/tasks/<uuid>', methods=['GET'])
def get_job_status(uuid):
    """Get the status of the task. ``GET /task/{uuid}/status``

    :param uuid: task identifier
    :return: JSON response with current job completion status
    """
    job_request = documents.JobRequest.find_one(
        mongo.slivkadb, uuid=uuid
    )
    if job_request is None:
        raise abort(404)
    return JsonResponse({
        'statuscode': 200,
        'status': job_request.status.name,
        'ready': job_request.status.is_finished(),
        'filesURI': flask.url_for('get_job_files', uuid=uuid)
    })


@app.route('/tasks/<uuid>', methods=['DELETE'])
def cancel_task(_):
    raise NotImplementedError


OutputFile = namedtuple('OutputFile', 'uuid, title, location, media_type')


@app.route('/tasks/<uuid>/files', methods=['GET'])
def get_job_files(uuid):
    """Get the list of output files. ``GET /task/{task_id}/files``

    :param uuid: task identifier
    :return: JSON response with list of files produced by the task.
    """
    job = documents.JobMetadata.find_one(
        mongo.slivkadb, uuid=uuid
    )
    if job is None:
        raise abort(404)
    if job.status == JobStatus.PENDING:
        return JsonResponse({
            'statuscode': 200,
            'files': []
        }, status=200)

    service_conf = slivka.settings.get_service_configuration(job.service)
    work_dir = pathlib.Path(job.work_dir)
    output_files = [
        OutputFile(
            uuid='%s/%s' % (job.uuid, path.name),
            title=path.name,
            location=path.relative_to(slivka.settings.TASKS_DIR).as_posix(),
            media_type=out.get('media-type')
        )
        for out in service_conf.execution_config['outputs'].values()
        for path in work_dir.glob(out['path'])
    ]

    return JsonResponse({
        'statuscode': 200,
        'files': [
            {
                'uuid': file.uuid,
                'title': file.title,
                'mimetype': file.media_type,
                'URI': flask.url_for('get_file_metadata', uid=file.uuid),
                'contentURI': flask.url_for('outputs', location=file.location)
            }
            for file in output_files
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
            job_request = form.save(mongo.slivkadb)
            url = flask.url_for('get_job_status', uuid=job_request.uuid)
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
