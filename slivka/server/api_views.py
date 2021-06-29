import base64
import datetime
import fnmatch
import os.path
import pathlib
from operator import attrgetter
from typing import Type

import flask
import pkg_resources
from bson import ObjectId
from flask import request, url_for, jsonify
from werkzeug.datastructures import FileStorage

import slivka.conf
from slivka.conf import ServiceConfig
from slivka.db.documents import (ServiceState, JobRequest, CancelRequest,
                                 JobMetadata, UploadedFile)
from slivka.db.helpers import insert_one
from .forms.form import BaseForm

bp = flask.Blueprint('api', __name__, url_prefix='/api/v1.1')

_DATETIME_STRF = "%Y-%m-%dT%H:%M:%S"


@bp.route('/version', endpoint='version', methods=['GET'])
def version_view():
    return jsonify(
        slivkaVersion=slivka.__version__,
        APIVersion="1.1"
    )


@bp.route('/services', endpoint='services', methods=['GET'])
def services_view():
    content = list(map(_service_resource, slivka.conf.settings.services))
    return jsonify(services=content)


@bp.route('/services/<service_id>', endpoint='service', methods=['GET'])
def service_view(service_id):
    service = next(filter(lambda srv: srv.id == service_id, slivka.conf.settings.services), None)
    if service is None:
        flask.abort(404)
    content = _service_resource(service)
    response = jsonify(content)
    response.headers['Location'] = content['@url']
    return response


def _service_resource(service: ServiceConfig):
    cursor = ServiceState.find(slivka.db.database, service=service.id)
    status = max(cursor, key=attrgetter('status'), default=None)
    if status is not None:
        status = {
            'status': status.status.name,
            'errorMessage': status.message,
            'timestamp': status.timestamp.strftime(_DATETIME_STRF)
        }
    else:
        status = {
            'status': 'UNKNOWN',
            'errorMessage': "",
            'timestamp': datetime.datetime.now().strftime(_DATETIME_STRF)
        }
    form: Type[BaseForm] = flask.current_app.config['forms'][service.id]
    return {
        '@url': url_for('.service', service_id=service.id),
        'id': service.id,
        'name': service.name,
        'description': service.description,
        'author': service.author,
        'version': service.version,
        'license': service.license,
        'classifiers': service.classifiers,
        'parameters': [field.__json__() for field in form],
        'presets': [],
        'status': status,
    }


@bp.route('/services/<service_id>/jobs',
          endpoint='service_jobs', methods=['POST'])
def service_jobs_view(service_id):
    service = flask.current_app.config['services'].get(service_id)
    if service is None:
        flask.abort(404)
    form_cls: Type[BaseForm] = flask.current_app.config['forms'][service_id]
    form = form_cls(flask.request.form, flask.request.files)
    if form.is_valid():
        job_request = form.save(
            slivka.db.database, slivka.conf.settings.directory.uploads)
        content = _job_resource(job_request)
        response = jsonify(content)
        response.status_code = 202
        response.headers['Location'] = content['@url']
    else:
        response = jsonify(errors=[
            {
                'parameter': field,
                'errorCode': error.code,
                'message': error.message
            }
            for field, error in form.errors.items()
        ])
        response.status_code = 400
    return response


@bp.route('/services/<service_id>/jobs/<job_id>',
          endpoint="service_job", methods=['GET', 'DELETE'])
@bp.route('/jobs/<job_id>', endpoint="job", methods=['GET', 'DELETE'])
def job_view(job_id, service_id=None):
    query = {'uuid': job_id}
    if service_id is not None:
        query['service'] = service_id
    job_request = JobRequest.find_one(slivka.db.database, **query)
    if job_request is None:
        flask.abort(404)
    if flask.request.method == 'GET':
        content = _job_resource(job_request)
        response = jsonify(content)
        response.headers['Location'] = content['@url']
        return response
    if flask.request.method == 'DELETE':
        cancel_req = CancelRequest(uuid=job_id)
        insert_one(slivka.db.database, cancel_req)
        return flask.Response(status=204)


def _job_resource(job_request: JobRequest):
    def convert_path(value):
        if not value:
            return value
        if isinstance(value, list):
            return list(map(convert_path, value))
        if os.path.isabs(value):
            value = pathlib.Path(value)
            base_path = flask.current_app.config['uploads_dir']
            try:
                return value.relative_to(base_path).as_posix()
            except ValueError:
                base_path = flask.current_app.config['jobs_dir']
                try:
                    return value.relative_to(base_path).as_posix()
                except ValueError:
                    return value

    parameters = {key: convert_path(val) for key, val in job_request.inputs.items()}
    return {
        '@url': url_for('.job', job_id=job_request.uuid),
        'id': job_request.uuid,
        'service': job_request.service,
        'parameters': parameters,
        'submissionTime': job_request.submission_time.strftime(_DATETIME_STRF),
        'completionTime': (
            job_request.completion_time and
            job_request.completion_time.strftime(_DATETIME_STRF)
        ),
        'status': job_request.status.name
    }


@bp.route('/jobs/<job_id>/files', endpoint='job_files', methods=['GET'])
def job_files_view(job_id):
    req = JobRequest.find_one(slivka.db.database, uuid=job_id)
    if req is None:
        flask.abort(404)
    job = JobMetadata.find_one(slivka.db.database, uuid=job_id)
    if job is None:
        return jsonify(files=[])
    service: ServiceConfig = flask.current_app.config['services'][job.service]
    dir_list = [
        os.path.relpath(os.path.join(base, fn), job.cwd)
        for base, _dir_names, file_names in os.walk(job.cwd)
        for fn in file_names
    ]
    files = [
        {
            '@url': url_for('.job_file', job_id=job_id, file_path=path),
            '@content': url_for('media.jobs', job_id=job_id, file_path=path),
            'id': f"{job_id}/{path}",
            'jobId': job_id,
            'path': path,
            'label': output.name,
            'mediaType': output.media_type
        }
        for output in service.outputs
        for path in fnmatch.filter(dir_list, output.path)
    ]
    return jsonify(files=files)


@bp.route('/jobs/<job_id>/files/<path:file_path>', 
          endpoint='job_file', methods=['GET'])
def job_file_view(job_id, file_path):
    job = JobMetadata.find_one(slivka.db.database, uuid=job_id)
    if job is None:
        flask.abort(404)
    service: ServiceConfig = flask.current_app.config['services'][job.service]
    if not os.path.isfile(os.path.join(job.cwd, file_path)):
        flask.abort(404)
    output_file = next(
        filter(lambda it: fnmatch.fnmatch(file_path, it.path), service.outputs),
        None
    )
    if output_file is None:
        flask.abort(404)
    location = url_for('.job_file', job_id=job_id, file_path=file_path)
    response = jsonify({
        '@url': location,
        '@content': url_for('media.jobs', job_id=job_id, file_path=file_path),
        'id': f"{job_id}/{file_path}",
        'jobId': job_id,
        'path': file_path,
        'label': output_file.name,
        'mediaType': output_file.media_type
    })
    response.headers['Location'] = location
    return response


@bp.route('/files', endpoint='files', methods=['POST'])
def files_view():
    file: FileStorage = request.files.get('file')
    if file is None:
        err_msg = ("Multipart form 'file' parameter not provided "
                   "or does not contain a file.")
        flask.abort(400, err_msg)
    oid = ObjectId()
    filename = base64.urlsafe_b64encode(oid.binary).decode()
    path = os.path.join(
        flask.current_app.config['uploads_dir'], filename
    )
    file.seek(0)
    file.save(path)
    insert_one(slivka.db.database, UploadedFile(_id=oid, path=path))
    location = url_for('.file', file_id=filename)
    response = jsonify({
        '@url': location,
        '@content': url_for('media.uploads', file_path=filename),
        'id': filename,
        'jobId': None,
        'path': filename,
        'label': 'uploaded',
        'mediaType': ""
    })
    response.status_code = 201
    response.headers['Location'] = location
    return response


@bp.route('/files/<file_id>', endpoint='file', methods=['GET'])
def file_view(file_id):
    path = os.path.join(flask.current_app.config['uploads_dir'], file_id)
    if not os.path.isfile(path):
        flask.abort(404)
    location = url_for('.file', file_id=file_id)
    response = jsonify({
        '@url': location,
        '@content': url_for('media.uploads', file_path=file_id),
        'id': file_id,
        'jobId': None,
        'path': file_id,
        'label': 'uploaded',
        'mediaType': ""
    })
    response.headers['Location'] = location
    return response


@bp.route('/')
@bp.route('/reference')
def api_reference_view():
    path = pkg_resources.resource_filename('slivka', 'data/swagger-ui-dist/')
    return flask.send_from_directory(path, 'index.html')


@bp.route('/swagger/openapi.yaml')
def openapi_yaml_view():
    stream = pkg_resources.resource_stream(
        'slivka', 'data/openapi-docs/openapi.yaml'
    )
    return flask.send_file(stream, 'application/yaml', as_attachment=False)


@bp.route('/swagger/<path:filename>')
def static_api_view(filename=None):
    path = pkg_resources.resource_filename('slivka', 'data/swagger-ui-dist/')
    return flask.send_from_directory(path, filename)
