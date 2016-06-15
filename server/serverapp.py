from flask import Flask, Response, json, request, abort, jsonify

from db import Session
from server.forms import get_form
import settings


app = Flask('PyBioAS')


@app.route('/')
def index():
    return "Hello, welcome to PyBioAS main page"


@app.route('/api/services', methods=['GET'])
def get_services():
    data = json.dumps({
        "services": settings.SERVICES
    }, indent=4)
    return Response(
        response=data,
        status=200,
        mimetype="application/json"
    )


@app.route('/api/service/<service>/form', methods=["GET"])
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


@app.route('/api/service/<service>/form', methods=["POST"])
def post_service_form(service):
    if service not in settings.SERVICES:
        abort(404)
    form_cls = get_form(service)
    form = form_cls(request.form)
    if form.is_valid():
        session = Session()
        form.save(session)
        session.commit()
        return Response(
            response=json.dumps({"form": form.cleaned_data}, indent=4),
            status=200,
            mimetype="application/json"
        )
    else:
        return str(form.fields)


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
