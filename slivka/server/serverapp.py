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
import sqlalchemy.orm.exc
import werkzeug.exceptions
import werkzeug.utils
from flask import Flask, Response, json, request, abort

import slivka
from slivka.db import Session, models, start_session
from slivka.server.forms import get_form
from slivka.utils import snake_to_camel

app = Flask('slivka', root_path=os.path.dirname(__file__))
"""Flask object implementing WSGI application."""


signer = itsdangerous.Signer(app.config["SECRET_KEY"])


@app.route('/services', methods=['GET'])
def get_services():
    """Return the list of services. ``GET /services``

    :return: JSON response with list of service names
    """
    return JsonResponse({"services": slivka.settings.SERVICES})


@app.route('/service/<service>/form', methods=["GET"])
def get_service_form(service):
    """Gets service request form. ``GET /service/{service}/form``

    :param service: service name
    :return: JSON response with service form
    """
    if service not in slivka.settings.SERVICES:
        raise abort(404)
    form_cls = get_form(service)
    form = form_cls()
    response = {
        "form": form_cls.__name__,
        "service": service,
        "fields": [
            {
                "name": field.name,
                "type": field.type,
                "required": field.required,
                "default": field.default,
                "constraints": [
                    {
                        "name": snake_to_camel(constraint['name']),
                        "value": constraint['value']
                    }
                    for constraint in field.constraints
                ]
            }
            for field in form.fields
        ]
    }
    return JsonResponse(response, status=200)


@app.route('/service/<service>/form', methods=["POST"])
def post_service_form(service):
    """Send form data and starts new task. ``POST /service/{service}/form``
    
    :param service: service name
    :return: JSON response with submitted task id
    """
    if service not in slivka.settings.SERVICES:
        raise abort(404)
    form_cls = get_form(service)
    form = form_cls(request.form)
    if form.is_valid():
        with start_session() as session:
            job_request = form.save(session)
            session.commit()
            response = JsonResponse({
                "taskId": job_request.uuid
            }, status=202)
    else:
        response = JsonResponse({
            "errors": [{
                "field": name,
                "errorCode": error.code,
                "message": error.reason
            } for name, error in form.errors.items()]
        }, status=420)
    return response


@app.route('/file', methods=["POST"])
def file_upload():
    """Upload the file to the server. ``POST /file``

    :return: JSON containing internal metadata of the uploaded file
    """
    try:
        mimetype = request.form["mimetype"]
    except KeyError:
        return JsonResponse({"error": "no mimetype"}, 400)
    try:
        file = request.files["file"]
    except KeyError:
        return JsonResponse({"error": "no file"}, 400)
    filename = werkzeug.utils.secure_filename(file.filename)
    with tempfile.NamedTemporaryFile(
            dir=app.config['MEDIA_DIR'], delete=False) as tf:
        file.save(tf)
    file_record = models.File(
        title=filename,
        mimetype=mimetype,
        path=tf.name
    )
    with start_session() as session:
        session.add(file_record)
        session.commit()
        file_id = file_record.id
    return JsonResponse({
        "id": file_id,
        "signedId":
            signer.sign(itsdangerous.want_bytes(file_id)).decode('utf-8'),
        "title": filename,
        "mimetype": mimetype
    }, status=203)


@app.route('/file/<file_id>', methods=["GET"])
def get_file_meta(file_id):
    """Get file metadata. ``GET /file/{file_id}``
    
    :param file_id: file identifier
    :return: JSON containing internal metadata of the file 
    """
    session = Session()
    try:
        file = (session.query(models.File).
                filter(models.File.id == file_id).
                one())
    except sqlalchemy.orm.exc.NoResultFound:
        raise abort(404)
    finally:
        session.close()
    return JsonResponse({
        "id": file.id,
        "title": file.title,
        "mimetype": file.mimetype
    }, status=200)


@app.route('/file/<file_id>/download', methods=["GET"])
def file_download(file_id):
    """Download file contents. ``GET /file/{file_id}/download``

    
    :param file_id: file identifier
    :return: requested file contents
    """
    with start_session() as session:
        query = (session.query(models.File).
                 filter(models.File.id == file_id))
        try:
            file = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)
        return flask.send_from_directory(
            directory=os.path.dirname(file.path),
            filename=os.path.basename(file.path),
            attachment_filename=file.title or os.path.basename(file.path),
            mimetype=file.mimetype
        )


@app.route('/file/<signed_file_id>', methods=["PUT"])
def set_file_meta(signed_file_id):
    """Update file metadata. ``PUT /file/{signed_file_id}``

    
    :param signed_file_id: signed file identifier
    :return: JSON containing new metadata of the file 
    """
    try:
        file_id = signer.unsign(signed_file_id).decode('utf-8')
    except itsdangerous.BadSignature:
        return JsonResponse({'error': "invalid signature"}, 403)
    with start_session() as session:
        try:
            file = (session.query(models.File).
                    filter(models.File.id == file_id).
                    one())
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)
        new_title = request.form.get("title")
        if new_title is not None:
            file.title = new_title
        session.commit()
        return JsonResponse({
            "id": file.id,
            "title": file.title,
            "mimetype": file.mimetype
        }, status=200)


@app.route('/file/<signed_file_id>', methods=["DELETE"])
def delete_file(signed_file_id):
    """Delete file from the filesystem. ``DELETE /file/{signed_file_id}``

    
    :param signed_file_id: signed file identifier
    :return: Http response with status code
    """
    try:
        file_id = signer.unsign(signed_file_id).decode('utf-8')
    except itsdangerous.BadSignature:
        return JsonResponse({'error': "invalid signature"}, 403)
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
    return Response(status=204)


@app.route('/task/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """Get the status of the task. ``GET /task/{task_id}/status``
    
    :param task_id: task identifier
    :return: JSON response with current job completion status
    """
    with start_session() as session:
        try:
            job_req = (session.query(models.Request).
                       filter_by(uuid=task_id).
                       one())
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)
        return JsonResponse({
            "status": job_req.status,
            "ready": job_req.is_finished
        })


@app.route('/task/<task_id>/files', methods=['GET'])
def get_task_files(task_id):
    """Get the list of file ids of this job. ``GET /task/{task_id}/files``

    :param task_id: task identifier
    :return: JSON response with list of file ids produced by the task.
    """
    with start_session() as session:
        try:
            req = (session.query(models.Request).
                   filter_by(uuid=task_id).
                   one())
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)

        files = (session.query(models.File).
                 filter_by(job=req.job).
                 all())
        return JsonResponse({
            "files": [file.id for file in files]
        })


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


# noinspection PyUnusedLocal
@app.errorhandler(404)
def not_found_404(e):
    """Custom 404 error JSON response."""
    return JsonResponse({"error": "not found"}, 404)


# noinspection PyUnusedLocal
@app.errorhandler(405)
def not_allowed_405(e):
    """Custom 405 error JSON response."""
    return JsonResponse({"error": "method not allowed"}, 405)


# noinspection PyUnusedLocal
@app.errorhandler(500)
def server_error_500(e):
    """Custom 500 error JSON resoinse."""
    return JsonResponse({"error": "internal server error"}, 500)


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
        mimetype="application/json",
        **kwargs
    )