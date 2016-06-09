import configparser

from flask import Flask, jsonify, request

from .config import services, service_info


app = Flask('PyBioAS')


@app.route('/')
def index():
    return "Hello, welcome to PyBioAS main page"


@app.route('/api/services', methods=['GET'])
def get_services():
    return jsonify(
        services=services
    )


@app.route('/api/service/<service>/info')
def get_service_info(service):
    info = service_info.get(service)
    if info is not None:
        return jsonify(
            name=service,
            options=info.options
        )


@app.route('/echo', methods=['GET', 'POST', 'PUT', 'DELETE'])
def echo():
    return jsonify(
        method=request.method,
        args=request.args,
        form=request.form
    )
