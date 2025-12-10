import base64
import fnmatch
import os.path
import pathlib
from datetime import datetime
from operator import attrgetter
from typing import Type

import flask
import pymongo.database
from bson import ObjectId
from flask import request, url_for, jsonify, current_app
from werkzeug.datastructures import FileStorage, MultiDict

import slivka.conf
from slivka import JobStatus
from slivka.compat import resources
from slivka.conf import ServiceConfig
from slivka.db.documents import JobRequest, CancelRequest, UploadedFile
from slivka.db.helpers import insert_one, push_one
from slivka.db.repositories import ServiceStatusRepository, UsageStatsRepository, RequestsRepository
from slivka.utils.path import *
from .forms.fields import FileField, ChoiceField
from .forms.file_proxy import FileProxy
from .forms.form import BaseForm
from ..utils.exceptions import IllegalFileNameError

bp = flask.Blueprint('api-v1_1', __name__, url_prefix='/api/v1.1')


@bp.route('/version', endpoint='version', methods=['GET'])
def version_view():
    return jsonify(
        slivkaVersion=slivka.__version__,
        APIVersion="1.1"
    )


@bp.route('/stats', endpoint='stats', methods=['GET'])
def usage_stats_view():
    stats_repo = UsageStatsRepository(slivka.db.database)
    return jsonify(usageStatictics=[
        {
            "month": entry.month.strftime("%Y-%m"),
            "service": entry.service,
            "count": entry.count,
        }
        for entry in stats_repo.list_all()
    ])


@bp.route('/services', endpoint='services', methods=['GET'])
def services_view():
    content = list(map(_service_resource, current_app.config['services'].values()))
    return jsonify(services=content)


@bp.route('/services/<service_id>', endpoint='service', methods=['GET'])
def service_view(service_id):
    service = current_app.config['services'].get(service_id)
    if service is None:
        flask.abort(404)
    content = _service_resource(service)
    response = jsonify(content)
    response.headers['Location'] = content['@url']
    return response


def _service_resource(service: ServiceConfig):
    status_repo = ServiceStatusRepository(slivka.db.database)
    service_statuses = status_repo.list_current(service=service.id)
    status = max(service_statuses, key=attrgetter('status'), default=None)
    if status is not None:
        status = {
            'status': status.status.name,
            'errorMessage': status.message,
            'timestamp': status.timestamp.astimezone().isoformat()
        }
    else:
        status = {
            'status': 'UNKNOWN',
            'errorMessage': "",
            'timestamp': datetime.fromtimestamp(0).isoformat()
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
    form_cls: Type[BaseForm] = flask.current_app.config['forms'][service.id]

    form_data = MultiDict()
    files = MultiDict()
    file_proxy_to_file_storage = []
    for key, file_storage in flask.request.files.items(multi=True):
        file_proxy = FileProxy(file=file_storage)
        files.add(key, file_proxy)
        file_proxy_to_file_storage.append((file_proxy, file_storage))
    file_proxy_to_file_name = []
    for name, value in flask.request.form.items(multi=True):
        if not isinstance(form_cls.get(name), FileField):
            form_data.add(name, value)
            continue
        file_id, *options = value.split(';')
        if not options:
            form_data.add(name, value)
            continue
        # for now, only the filename option exists
        if not options[0].startswith("filename="):
            flask.abort(400, f"Illegal value for parameter {name}: '{value}'")
        file_name = options[0][len("filename="):]
        file_proxy = FileProxy.from_id(file_id, slivka.db.database)
        files.add(name, file_proxy)
        file_proxy_to_file_name.append((file_proxy, file_name))

    form = form_cls(form_data, files)
    if form.is_valid():
        for file_proxy, file_storage in file_proxy_to_file_storage:
            uploaded_file = save_uploaded_file(
                file_storage, current_app.config['uploads_dir'], slivka.db.database)
            # set file_proxy.path so that the following form.save can write
            # the request parameters to the database. FileField.to_arg()
            # requires `path` to be set.
            file_proxy.path = uploaded_file.path
        for file_proxy, file_name in file_proxy_to_file_name:
            uploaded_file = remake_uploaded_file(
                file_proxy,
                file_name,
                current_app.config['uploads_dir'],
                slivka.db.database
            )
            file_proxy.path = uploaded_file.path
        job_request = form.save(
            slivka.db.database, current_app.config['uploads_dir'])
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
        response.status_code = 422
    return response


@bp.route('/services/<service_id>/jobs',
          endpoint='service_jobs_list', methods=['GET'])
@bp.route('/jobs/', endpoint="jobs_list", methods=['GET'])
def jobs_list_view(service_id=None):
    repo = RequestsRepository(slivka.db.database)
    filters = []
    if service_id:
        service = flask.current_app.config['services'].get(service_id)
        filters.append(('service', service.id))
    limit = None
    skip = 0
    try:
        for key, val in request.args.items(multi=True):
            if key == "limit":
                limit = int(val)
            elif key == "skip":
                skip = int(val)
            elif key == "status":
                try:
                    filters.append(("status", JobStatus[val.upper()]))
                except KeyError:
                    raise ValueError(f"invalid value: {val}")
            elif key in ("id", "service", "submissionTime", "status"):
                filters.append((key, val))
            else:
                raise ValueError(f"illegal argument: {key}")
        job_requests = repo.list(filters=filters, limit=limit, skip=skip)
        return jsonify({
            "totalCount": repo.count(filters),
            "jobs": [_job_resource(req) for req in job_requests]
        })
    except ValueError as e:
        flask.abort(400, str(e))


@bp.route('/services/<service_id>/jobs/<job_id>',
          endpoint="service_job", methods=['GET', 'DELETE'])
@bp.route('/jobs/<job_id>', endpoint="job", methods=['GET', 'DELETE'])
def job_view(job_id, service_id=None):
    query = {'id': job_id}
    if service_id is not None:
        service = flask.current_app.config['services'].get(service_id)
        query['service'] = service.id
    job_request = JobRequest.find_one(slivka.db.database, **query)
    if job_request is None:
        flask.abort(404)
    if flask.request.method == 'GET':
        content = _job_resource(job_request)
        response = jsonify(content)
        response.headers['Location'] = content['@url']
        return response
    if flask.request.method == 'DELETE':
        cancel_req = CancelRequest(job_id=job_request.id)
        insert_one(slivka.db.database, cancel_req)
        return flask.Response(status=204)


def _job_resource(job_request: JobRequest):
    def convert_path(value):
        if os.path.isabs(value):
            path = pathlib.Path(value).resolve()
            base_path = flask.current_app.config['uploads_dir']
            try:
                return path.relative_to(base_path).as_posix()
            except ValueError:
                pass
            base_path = flask.current_app.config['jobs_dir']
            try:
                return job_file_path_to_file_id(base_path, path)
            except ValueError:
                return value
        return value

    def convert_choice(choices):
        def unmap(value):
            return next((k for k, v in choices.items() if v == value), value)

        return unmap

    def convert_parameter(key, val):
        if not val:
            return val
        nonlocal form
        field = form[key]
        if isinstance(field, FileField):
            convert = convert_path
        elif isinstance(field, ChoiceField):
            convert = convert_choice(field.choices)
        else:
            return val
        if isinstance(val, list):
            return list(map(convert, val))
        return convert(val)

    form: BaseForm = flask.current_app.config['forms'].get(job_request.service)
    parameters = {
        key: convert_parameter(key, val)
        for key, val in job_request.inputs.items()
    }
    return {
        '@url': url_for('.job', job_id=job_request.b64id),
        'id': job_request.b64id,
        'service': job_request.service,
        'parameters': parameters,
        'submissionTime': job_request.submission_time.astimezone().isoformat(),
        'completionTime': (
                job_request.status.is_finished() and
                job_request.completion_time and
                job_request.completion_time.astimezone().isoformat() or None
        ),
        'finished': job_request.status.is_finished(),
        'status': job_request.status.name
    }


@bp.route('/jobs/<job_id>/files', endpoint='job_files', methods=['GET'])
def job_files_view(job_id):
    req = JobRequest.find_one(slivka.db.database, id=job_id)
    if req is None:
        flask.abort(404)
    job = req.job
    if job is None:
        return jsonify(files=[])
    service: ServiceConfig = flask.current_app.config['services'][req.service]
    dir_list = [
        os.path.relpath(os.path.join(base, fn), job.cwd)
        for base, _dir_names, file_names in os.walk(job.cwd)
        for fn in file_names
    ]
    files = [
        _job_file_resource(job_request=req, output_def=output, rel_path=path)
        for output in service.outputs
        for path in fnmatch.filter(dir_list, output.path)
    ]
    return jsonify(files=files)


@bp.route('/jobs/<job_id>/files/<path:file_path>',
          endpoint='job_file', methods=['GET'])
def job_file_view(job_id, file_path):
    req = JobRequest.find_one(slivka.db.database, id=job_id)
    if req is None:
        flask.abort(404)
    job = req.job
    if job is None:
        flask.abort(404)
    service: ServiceConfig = flask.current_app.config['services'][req.service]
    if not os.path.isfile(os.path.join(job.cwd, file_path)):
        flask.abort(404)
    output_file = next(
        filter(lambda it: fnmatch.fnmatch(file_path, it.path), service.outputs),
        None
    )
    if output_file is None:
        flask.abort(404)

    body = _job_file_resource(
        job_request=req, output_def=output_file, rel_path=file_path
    )
    response = jsonify(body)
    response.headers['Location'] = body["@url"]
    return response


def _job_file_resource(job_request: JobRequest,
                       output_def: ServiceConfig.OutputFile,
                       rel_path: str):
    job_id = job_request.b64id
    resource_location = url_for(".job_file", job_id=job_id, file_path=rel_path)
    jobs_dir = flask.current_app.config["jobs_dir"]
    # make job_cwd canonical for consistency with "jobs_dir" config
    job_cwd: str = os.path.realpath(job_request.job.cwd)
    base_path = os.path.relpath(job_cwd, jobs_dir)
    full_path = os.path.join(base_path, rel_path)
    if os.path.sep == "\\":
        rel_path = rel_path.replace("\\", "/")
        full_path = full_path.replace("\\", "/")
    content_location = url_for("media.jobs", file_path=full_path)
    return {
        "@url": resource_location,
        "@content": content_location,
        "id": f"{job_id}/{rel_path}",
        "jobId": job_id,
        "path": rel_path,
        "label": output_def.name or output_def.id,
        "mediaType": output_def.media_type,
    }


@bp.route('/files', endpoint='files', methods=['POST'])
def files_view():
    file: FileStorage = request.files.get('file')
    if file is None:
        err_msg = ("Multipart form 'file' parameter not provided "
                   "or does not contain a file.")
        flask.abort(400, err_msg)
    uploaded_file = save_uploaded_file(
        file,
        flask.current_app.config['uploads_dir'],
        slivka.db.database
    )
    body = _uploaded_file_resource(uploaded_file)
    response = jsonify(body)
    response.status_code = 201
    response.headers['Location'] = body["@url"]
    return response


def save_uploaded_file(file: FileStorage, directory, database):
    oid = ObjectId()
    filename = base64.urlsafe_b64encode(oid.binary).decode()
    save_path = os.path.join(directory, filename)
    file.seek(0)
    file.save(save_path)
    try:
        uploaded_file = UploadedFile(_id=oid, title=file.filename, media_type=file.mimetype, path=save_path)
    except IllegalFileNameError as e:
        flask.abort(400, f"Illegal filename: {e.filename}")
    insert_one(database, uploaded_file)
    return uploaded_file


def remake_uploaded_file(
        file: FileProxy,
        title: str,
        directory: os.PathLike,
        database: pymongo.database.Database
):
    oid = ObjectId()
    filename = base64.urlsafe_b64encode(oid.binary).decode()
    new_path = os.path.join(directory, filename)
    os.symlink(file.path, new_path)
    try:
        uploaded_file = UploadedFile(_id=oid, title=title, path=new_path)
    except IllegalFileNameError as e:
        flask.abort(400, f"Illegal filename: {e.filename}")
    insert_one(database, uploaded_file)
    return uploaded_file


@bp.route('/files/<file_id>', endpoint='file', methods=['GET', 'PUT'])
def file_view(file_id):
    uploaded_file = UploadedFile.find_one(slivka.db.database, id=file_id)
    if not uploaded_file:
        flask.abort(404)
    if request.method == "PUT":
        if "label" in request.form:
            try:
                uploaded_file.title = request.form["label"]
            except IllegalFileNameError as e:
                flask.abort(400, f"Illegal filename: {e.filename}")
        if "mediaType" in request.form:
            uploaded_file.media_type = request.form["mediaType"]
        push_one(slivka.db.database, uploaded_file)
    body = _uploaded_file_resource(uploaded_file)
    response = jsonify(body)
    response.headers['Location'] = body["@url"]
    return response


def _uploaded_file_resource(uploaded_file: UploadedFile):
    file_id = uploaded_file.b64id
    uploads_dir = flask.current_app.config["uploads_dir"]
    path = os.path.relpath(uploaded_file.path, uploads_dir)
    if os.path.sep == "\\":
        path = path.replace("\\", "/")
    return {
        "@url": url_for(".file", file_id=file_id),
        "@content": url_for("media.uploads", file_path=path),
        "id": file_id,
        "jobId": None,
        "path": path,
        "label": uploaded_file.title,
        "mediaType": uploaded_file.media_type,
    }


@bp.route('/')
@bp.route('/reference')
def api_reference_view():
    app_home = flask.current_app.config['home']
    path = os.path.join(app_home, 'static', 'redoc-index.html')
    if os.path.exists(path):
        return flask.send_file(path)
    else:
        # load file from the package for backwards compatibility
        stream = resources.open_binary(
            'slivka', 'project_template/static/redoc-index.html')
        return flask.send_file(stream, 'text/html')


@bp.route('/openapi.yaml')
def openapi_view():
    app_home = flask.current_app.config['home']
    path = os.path.join(app_home, 'static', 'openapi.yaml')
    if os.path.exists(path):
        return flask.send_file(path)
    else:
        # load file from the package for backwards compatibility
        stream = resources.open_binary(
            'slivka', 'project_template/static/openapi.yaml')
        return flask.send_file(stream, 'application/yaml')
