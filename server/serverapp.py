import os.path

import flask
import itsdangerous
import sqlalchemy.orm.exc
import werkzeug.exceptions
import werkzeug.utils
from flask import Flask, Response, json, request, abort, redirect

import settings
from db import Session, models, start_session
from server.forms import get_form


app = Flask('PyBioAS', root_path=os.path.dirname(__file__))
app.config.update(
    DEBUG=True,
    UPLOAD_DIR=settings.UPLOAD_DIR,
    SECRET_KEY=settings.SECRET_KEY
)

signer = itsdangerous.Signer(app.config["SECRET_KEY"])


@app.route('/')
def index():
    return redirect("/static/rest_api_specification.html")


@app.route('/services', methods=['GET'])
def get_services():
    return JsonResponse({"services": settings.SERVICES})


@app.route('/service/<service>/form', methods=["GET"])
def get_service_form(service):
    if service not in settings.SERVICES:
        raise abort(404)
    form_cls = get_form(service)
    form = form_cls()
    return JsonResponse(response=form.to_dict(), status=200)


@app.route('/service/<service>/form', methods=["POST"])
def post_service_form(service):
    if service not in settings.SERVICES:
        raise abort(404)
    form_cls = get_form(service)
    form = form_cls(request.form)
    if form.is_valid():
        with start_session() as session:
            job_request = form.save(session)
            session.commit()
            response = JsonResponse({
                "valid": True,
                "fields": [{
                    "name": field.name,
                    "value": field.cleaned_value
                } for field in form.fields],
                "task_id": job_request.uuid
            }, status=202)
    else:
        response = JsonResponse({
            "valid": False,
            "fields": [{
                "name": field.name,
                "value": field.value
            } for field in form.fields],
            "errors": [{
                "field": name,
                "error_code": error.code,
                "message": error.reason
            } for name, error in form.errors.items()]
        }, status=200)
    return response


@app.route('/file', methods=["POST"])
def file_upload():
    title = request.form.get("title", "")
    description = request.form.get("description", "")
    try:
        mimetype = request.form["mime-type"]
    except KeyError:
        return JsonResponse({"error": "no mime-type"}, 400)
    if not mimetype.startswith("text/"):
        return JsonResponse({"error": "invalid mime-type"}, 415)
    try:
        file = request.files["file"]
    except KeyError:
        return JsonResponse({"error": "no file"}, 400)
    filename = werkzeug.utils.secure_filename(file.filename)
    file_record = models.File(
        title=title,
        description=description,
        mimetype=mimetype,
        filename=filename
    )
    with start_session() as session:
        session.add(file_record)
        session.commit()
        file_id = file_record.id
    file.save(os.path.join(app.config['UPLOAD_DIR'], file_id))
    return JsonResponse({
        "id": file_id,
        "signed_id":
            signer.sign(itsdangerous.want_bytes(file_id)).decode('utf-8'),
        "title": title,
        "description": description,
        "mime-type": mimetype,
        "filename": filename
    }, status=203)


@app.route('/file/<file_id>', methods=["GET"])
def get_file_meta(file_id):
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
        "description": file.description,
        "mime-type": file.mimetype,
        "filename": file.filename
    })


@app.route('/file/<file_id>/download', methods=["GET"])
def file_download(file_id):
    with start_session() as session:
        query = (session.query(models.File.filename, models.File.mimetype).
                 filter(models.File.id == file_id))
        try:
            filename, mimetype = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)
        return flask.send_from_directory(
            directory=app.config["UPLOAD_DIR"],
            filename=file_id,
            attachment_filename=filename,
            mimetype=mimetype
        )


@app.route('/file/<signed_file_id>', methods=["PUT"])
def set_file_meta(signed_file_id):
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
        new_description = request.form.get("description")
        if new_description is not None:
            file.description = new_description
        new_filename = request.form.get("filename")
        if new_filename is not None:
            file.filename = new_filename
        session.commit()
        return JsonResponse({
            "id": file.id,
            "title": file.title,
            "description": file.description,
            "mime-type": file.mimetype,
            "filename": file.filename
        })


@app.route('/file/<signed_file_id>', methods=["DELETE"])
def delete_file(signed_file_id):
    try:
        file_id = signer.unsign(signed_file_id).decode('utf-8')
    except itsdangerous.BadSignature:
        return JsonResponse({'error': "invalid signature"}, 403)
    with start_session as session:
        num_deleted = (session.query(models.File).
                       filter(models.File.id == file_id).
                       delete())
        if num_deleted == 0:
            raise abort(404)
        session.commit()
    try:
        os.remove(os.path.join(app.config["UPLOAD_DIR"], file_id))
    except FileNotFoundError:
        raise abort(404)
    return Response(status=204)


@app.route('/task/<task_id>', methods=["GET"])
def get_task(task_id):
    with start_session() as session:
        try:
            job_request = (session.query(models.Request).
                           filter(models.Request.uuid == task_id).
                           one())
        except sqlalchemy.orm.exc.NoResultFound:
            raise abort(404)
        return JsonResponse({
            "status": job_request.status,
            "ready": job_request.is_finished,
            "output": {
                "returnCode": job_request.result.return_code,
                "stdout": job_request.result.stdout,
                "stderr": job_request.result.stderr
            }
        })


@app.route('/echo', methods=['GET', 'POST', 'PUT', 'DELETE'])
def echo():
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
    return JsonResponse({"error": "not found"}, 404)


# noinspection PyUnusedLocal
@app.errorhandler(405)
def not_allowed_405(e):
    return JsonResponse({"error": "method not allowed"}, 405)


# noinspection PyUnusedLocal
@app.errorhandler(500)
def server_error_500(e):
    return JsonResponse({"error": "internal server error"}, 500)


# noinspection PyPep8Naming
def JsonResponse(response, status=200, **kwargs):
    """
    A helper function creating json response
    :param response: dictionary representing response content
    :param status: HTTP response status code
    :param kwargs: arguments passed to the Response object
    :return: JSON response object
    """
    return Response(
        response=json.dumps(response, indent=4),
        status=status,
        mimetype="application/json",
        **kwargs
    )
