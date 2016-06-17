import os.path

from flask import Flask, Response, json, request, abort, redirect

from db import Session
from server.forms import get_form
import settings


app = Flask('PyBioAS', root_path=os.path.dirname(__file__))


@app.route('/')
def index():
    return redirect("/static/rest_api_specification.html")


@app.route('/services', methods=['GET'])
def get_services():
    data = json.dumps({
        "services": settings.SERVICES
    }, indent=4)
    return Response(
        response=data,
        status=200,
        mimetype="application/json"
    )


@app.route('/service/<service>/form', methods=["GET"])
def get_service_form(service):
    if service not in settings.SERVICES:
        abort(404)
    form_cls = get_form(service)
    form = form_cls()
    data = json.dumps(form.to_dict(), indent=4)
    return Response(
        response=data,
        status=200,
        mimetype="application/json"
    )


@app.route('/service/<service>/form', methods=["POST"])
def post_service_form(service):
    if service not in settings.SERVICES:
        abort(404)
    form_cls = get_form(service)
    form = form_cls(request.form)
    if form.is_valid():
        session = Session()
        job_request = form.save(session)
        session.commit()
        res = json.dumps({
            "valid": True,
            "fields": [
                {
                    "name": field.name,
                    "value": field.cleaned_value
                } for field in form.fields
            ],
            "task_id": job_request.uuid
        }, indent=4)
        session.close()
        return Response(
            response= res,
            status=202,
            mimetype="application/json"
        )
    else:
        fields = [
            {
                "name": field.name,
                "value": field.value
            }
            for field in form.fields
        ]
        errors = [
            {
                "field": field.name,
                "value": field.value,
                "error_code": field.error.code,
                "message": field.error.reason
            }
            for field in form.fields if field.error is not None
        ]
        return Response(
            response=json.dumps({
                "valid": False,
                "fields": fields,
                "errors": errors
            }, indent=4)
        )


@app.route('/echo', methods=['GET', 'POST', 'PUT', 'DELETE'])
def echo():
    data = json.dumps(dict(
        method=request.method,
        args=request.args,
        form=request.form
    ), indent=4)
    return Response(
        response=data,
        status=200,
        mimetype="application/json"
    )
