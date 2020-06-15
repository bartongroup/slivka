import os.path
import pathlib
from collections import namedtuple
from fnmatch import fnmatch
from tempfile import mkstemp

import flask
import pkg_resources
from flask import request, abort, url_for, current_app as app

import slivka
from slivka import JobStatus
from slivka.db import database, documents
from slivka.db.helpers import insert_one
from . import JsonResponse
from .forms import FormLoader
from ..db.documents import ServiceState

bp = flask.Blueprint('api', __name__, url_prefix='/api/v1')


@bp.route('/version', methods=['GET'])
def get_version():
    return JsonResponse({
        'statuscode': 200,
        'slivka': slivka.__version__,
        'api': '1.0'
    })


@bp.route('/services', methods=['GET'])
def get_services():
    """Return the list of services. ``GET /services``

    :return: JSON response with list of service names
    """
    return JsonResponse({
        'statuscode': 200,
        'services': [
            {
                'name': service.name,
                'label': service.label,
                'URI': url_for('.get_service_form', service=service.name),
                'classifiers': service.classifiers
            }
            for service in slivka.settings.services.values()
        ]
    })


@bp.route('/services/<service>', methods=['GET'])
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
        'URI': url_for('.post_service_form', service=service),
        'fields': [field.__json__() for field in form]
    }
    return JsonResponse(response, status=200)


@bp.route('/services/<service>', methods=['POST'])
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
        request_doc = form.save(database)
        resource_location = url_for('.get_job_status', uuid=request_doc.uuid)
        return JsonResponse(
            {
                'statuscode': 202,
                'uuid': request_doc.uuid,
                'URI': resource_location
            },
            status=202,
            headers={'Location': resource_location}
        )
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


@bp.route('/servicemonitor', methods=['GET'])
def service_monitor():
    states = ServiceState.find(slivka.db.database)
    return JsonResponse({
        'states': [
            {
                'service': state.service,
                'runner': state.runner,
                'state': state.state.name,
                'timestamp': state.timestamp.isoformat()
            }
            for state in states
        ]
    })



@bp.route('/services/<service>/presets', methods=['GET'])
def all_presets(service):
    try:
        conf = slivka.settings.services[service]
    except KeyError:
        raise abort(404)
    return JsonResponse({
        'statuscode': 200,
        'presets': list(conf.presets.values())
    })


@bp.route('/services/<service>/presets/<preset>', methods=['GET'])
def get_preset(service, preset):
    try:
        conf = slivka.settings.services[service]
        return JsonResponse({
            'statuscode': 200,
            'preset': conf.presets[preset]
        })
    except KeyError:
        raise abort(404)


@bp.route('/files', methods=['POST'])
def file_upload():
    """Upload the file to the server. ``POST /files``

    :return: JSON containing internal metadata of the uploaded file
    """
    try:
        file = request.files['file']
    except KeyError:
        raise abort(400)
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
    file_doc.insert(database)
    resource_location = url_for('.get_file_metadata', uid=file_doc.uuid)
    return JsonResponse(
        {
            'statuscode': 201,
            'uuid': file_doc.uuid,
            'title': file.filename,
            'label': 'uploaded',
            'mimetype': file.mimetype,
            'URI': resource_location,
            'contentURI': url_for('root.uploads', location=filename)
        },
        headers={'Location': resource_location},
        status=201
    )


@bp.route('/files/<path:uid>', methods=['GET'])
def get_file_metadata(uid):
    """Get file metadata. ``GET /file/{file_uuid}``

    :param uid: file identifier
    :return: JSON containing internal metadata of the file
    """
    tokens = uid.split('/', 1)
    if len(tokens) == 1:
        uuid, = tokens
        file = documents.UploadedFile.find_one(database, uuid=uuid)
        if file is None:
            raise abort(404)
        return JsonResponse({
            'statuscode': 200,
            'uuid': file['uuid'],
            'title': file['title'],
            'label': 'uploaded',
            'mimetype': file['media_type'],
            'URI': url_for('.get_file_metadata', uid=uid),
            'contentURI': url_for('root.uploads', location=file['basename'])
        })
    elif len(tokens) == 2:
        uuid, filename = tokens
        job = documents.JobMetadata.find_one(database, uuid=uuid)
        if job is None:
            raise abort(404)
        conf = slivka.settings.services[job.service]
        label, file_meta = next(
            (key, val) for (key, val) in conf.command['outputs'].items()
            if fnmatch(filename, val['path'])
        )
        file_location = '%s/%s' % (os.path.basename(job.work_dir), filename)
        return JsonResponse({
            'statuscode': 200,
            'uuid': uid,
            'title': filename,
            'label': label,
            'mimetype': file_meta.get('media-type'),
            'URI': url_for('.get_file_metadata', uid=uid),
            'contentURI': url_for('root.outputs', location=file_location)
        })
    else:
        raise abort(404)


@bp.route('/tasks/<uuid>', methods=['GET'])
def get_job_status(uuid):
    """Get the status of the task. ``GET /task/{uuid}/status``

    :param uuid: task identifier
    :return: JSON response with current job completion status
    """
    job_request = documents.JobRequest.find_one(database, uuid=uuid)
    if job_request is None:
        raise abort(404)
    return JsonResponse({
        'statuscode': 200,
        'status': job_request.status.name,
        'ready': job_request.status.is_finished(),
        'filesURI': url_for('.get_job_files', uuid=uuid)
    })


@bp.route('/tasks/<uuid>', methods=['DELETE'])
def cancel_task(uuid):
    job_request = documents.JobRequest.find_one(database, uuid=uuid)
    if job_request is None:
        raise abort(404)
    if not job_request.status.is_finished():
        insert_one(slivka.db.database,
                   documents.CancelRequest(job_request.uuid))
    return JsonResponse({'statuscode': 202}, status=202)


OutputFile = namedtuple('OutputFile', 'uuid, title, label, location, media_type')


@bp.route('/tasks/<uuid>/files', methods=['GET'])
def get_job_files(uuid):
    """Get the list of output files. ``GET /task/{task_id}/files``

    :param uuid: task identifier
    :return: JSON response with list of files produced by the task.
    """
    job = documents.JobMetadata.find_one(database, uuid=uuid)
    if job is None:
        raise abort(404)
    if job.status == JobStatus.PENDING:
        return JsonResponse({
            'statuscode': 200,
            'files': []
        }, status=200)

    service = slivka.settings.services[job.service]
    work_dir = pathlib.Path(job.work_dir)
    output_files = [
        OutputFile(
            uuid='%s/%s' % (job.uuid, path.name),
            title=path.name,
            label=key,
            location=path.relative_to(slivka.settings.jobs_dir).as_posix(),
            media_type=val.get('media-type')
        )
        for key, val in service.command['outputs'].items()
        for path in work_dir.glob(val['path'])
    ]

    return JsonResponse({
        'statuscode': 200,
        'files': [
            {
                'uuid': file.uuid,
                'title': file.title,
                'label': file.label,
                'mimetype': file.media_type,
                'URI': url_for('.get_file_metadata', uid=file.uuid),
                'contentURI': url_for('root.outputs', location=file.location)
            }
            for file in output_files
        ]
    }, status=200)


@bp.route('/')
@bp.route('/reference')
def api_index():
    path = pkg_resources.resource_filename('slivka', 'data/swagger-ui-dist/')
    return flask.send_from_directory(path, 'index.html')


@bp.route('/swagger/openapi.yaml')
def serve_openapi_yaml():
    stream = pkg_resources.resource_stream(
        'slivka', 'data/openapi-docs/openapi.yaml'
    )
    return flask.send_file(stream, 'application/yaml', as_attachment=False)


@bp.route('/swagger/<path:filename>')
def serve_api_static(filename=None):
    path = pkg_resources.resource_filename('slivka', 'data/swagger-ui-dist/')
    return flask.send_from_directory(path, filename)


@bp.route('/echo', methods=['GET', 'POST', 'PUT', 'DELETE'])
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


bp.register_error_handler(
    400, lambda e: error_response(400, 'Bad request')
)
bp.register_error_handler(
    401, lambda e: error_response(401, 'Unauthorized')
)
bp.register_error_handler(
    404, lambda e: error_response(404, 'Not found')
)
bp.register_error_handler(
    405, lambda e: error_response(405, 'Method not allowed')
)
bp.register_error_handler(
    415, lambda e: error_response(415, 'Unsupported media type')
)
bp.register_error_handler(
    500, lambda e: error_response(500, 'Internal server error')
)
bp.register_error_handler(
    503, lambda e: error_response(503, 'Service unavailable')
)
