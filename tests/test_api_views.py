import io
import os
import shutil
from datetime import datetime, timedelta
from functools import partial

import flask
import mongomock
import pkg_resources
import yaml
from nose import with_setup
from nose.tools import assert_in, assert_equal, assert_list_equal, \
    assert_dict_equal, assert_dict_contains_subset, assert_true, assert_false, \
    assert_almost_equal, assert_is_none

import slivka.db
import slivka.server
from slivka import JobStatus
from slivka.conf.loaders import load_settings_0_3
from slivka.db.documents import ServiceState, UploadedFile, JobRequest
from slivka.db.helpers import insert_one, push_one, insert_many


def load_app():
    project_location = pkg_resources.resource_filename(__name__, 'test_project')
    config_file = pkg_resources.resource_stream(__name__, 'test_project/config.yml')
    config = load_settings_0_3(yaml.safe_load(config_file), project_location)
    app = slivka.server.create_app(config)
    app.config['TESTING'] = True
    return app


def setup_database():
    slivka.db.mongo = mongomock.MongoClient()
    slivka.db.database = slivka.db.mongo.slivkadb
    return slivka.db.database


def teardown_database():
    del slivka.db.database
    del slivka.db.mongo


class TestServicesListView:
    @classmethod
    def setup_class(cls):
        cls.app = load_app()

    def setup(self):
        setup_database()

    def teardown(self):
        teardown_database()

    def test_services_list(self):
        with self.app.test_client() as client:
            response: flask.Response = client.get("/api/services")
            response = response.get_json()
        assert_in('services', response)
        service = response['services'][0]
        assert_equal(service['id'], 'fake')


class TestServiceView:
    app: flask.Flask = None

    @classmethod
    def setup_class(cls):
        cls.app = load_app()
        cls.database = setup_database()

    @classmethod
    def teardown_class(cls):
        teardown_database()

    def setup(self):
        with self.app.test_client() as client:
            self.response = client.get("/api/services/fake")
            self.json_content = self.response.get_json()

    def test_status_code(self):
        assert_equal(self.response.status_code, 200)

    def test_service_basic_info(self):
        expected = {
            '@url': '/api/services/fake',
            'id': 'fake',
            'name': "Fake service",
            'description': "Description of fake service",
            'author': "John Smith",
            'version': "0.6.7",
            'license': "Dummy License"
        }
        assert_dict_contains_subset(expected, self.json_content)

    def test_classifiers(self):
        assert_list_equal(
            self.json_content['classifiers'], ["Class::Test", "Group::Dummy"]
        )

    def test_default_status(self):
        assert_equal(self.json_content['status']['status'], 'UNKNOWN')

    def test_status(self):
        timestamp = datetime(2020, 1, 1, 12, 30, 51)
        state = ServiceState(service="fake", runner="default",
                             state=ServiceState.OK, message="OK",
                             timestamp=timestamp)
        insert_one(self.database, state)
        yield (
            self.assert_status_equal,
            {'status': "OK", 'errorMessage': "OK",
             'timestamp': "2020-01-01T12:30:51"}
        )
        state.state = ServiceState.WARNING
        state.message = "Service issues."
        push_one(self.database, state)
        yield (
            self.assert_status_equal,
            {'status': "WARNING", 'errorMessage': "Service issues.",
             'timestamp': "2020-01-01T12:30:51"}
        )
        state.state = ServiceState.DOWN
        state.message = "Service not operational."
        push_one(self.database, state)
        yield (
            self.assert_status_equal,
            {'status': "DOWN", 'errorMessage': "Service not operational.",
             'timestamp': "2020-01-01T12:30:51"}
        )

    def assert_status_equal(self, expected):
        assert_dict_equal(self.json_content['status'], expected)

    def test_parameters(self):
        expected = [
            {
                'type': "file",
                'id': 'file-param',
                'name': "File parameter",
                'description': "Input file",
                'required': False,
                'array': False,
                'default': None
            },
            {
                'type': 'text',
                'id': "text-param",
                'name': "Text parameter",
                'description': "Description of text parameter",
                'required': True,
                'array': False,
                'default': None
            },
            {
                'type': "decimal",
                'id': "number-param",
                'name': "Number parameter",
                'description': "Description of number parameter",
                'required': False,
                'array': False,
                'default': 0.1
            }
        ]
        assert_list_equal(self.json_content['parameters'], expected)


@with_setup(setup_database, teardown_database)
def test_missing_service():
    app = load_app()
    with app.test_client() as client:
        response = client.get("/api/services/nonexistent")
    assert_equal(response.status_code, 404)


class TestValidJobSubmissionView:
    app: flask.Flask = None

    @classmethod
    def setup_class(cls):
        cls.app = load_app()
        os.makedirs(cls.app.config['uploads_dir'])
        cls.database = setup_database()
        with cls.app.test_client() as client:
            cls.response = client.post(
                "/api/services/fake/jobs",
                content_type="multipart/form-data",
                data={
                    'text-param': "Hello world",
                    'number-param': 12.3,
                    'file-param': (io.BytesIO(b"Content"), 'input file')
                }
            )

    @classmethod
    def teardown_class(cls):
        teardown_database()
        shutil.rmtree(cls.app.config['uploads_dir'])

    def test_status_code(self):
        assert_equal(self.response.status_code, 202)

    def test_job_url(self):
        content = self.response.get_json()
        uid = content['id']
        assert_equal(content['@url'], f'/api/jobs/{uid}')

    def test_location_header(self):
        content = self.response.get_json()
        assert_equal(self.response.headers['Location'],
                     f"http://localhost{content['@url']}")

    def test_returned_service(self):
        content = self.response.get_json()
        assert_equal(content['service'], 'fake')

    def test_returned_status(self):
        content = self.response.get_json()
        assert_equal(content['status'], 'PENDING')

    def test_returned_parameters(self):
        content = self.response.get_json()
        file = UploadedFile.find_one(self.database)
        assert_dict_equal(
            content['parameters'],
            {
                'text-param': "Hello world",
                'number-param': "12.3",
                'file-param': file.b64id
            }
        )

    def test_saved_request(self):
        request = JobRequest.find_one(self.database)
        file = UploadedFile.find_one(self.database)
        yield assert_equal, request.service, "fake"
        yield (partial(assert_almost_equal, delta=timedelta(milliseconds=10)),
               request.timestamp, datetime.now())
        yield assert_equal, request.status, JobStatus.PENDING
        expected_inputs = {
            'text-param': "Hello world",
            'number-param': "12.3",
            'file-param': file.path
        }
        yield assert_dict_equal, request.inputs, expected_inputs

    def test_uploaded_file_path(self):
        file = UploadedFile.find_one(self.database)
        assert_true(os.path.isfile(file.path))
        relpath = os.path.relpath(file.path, self.app.config['uploads_dir'])
        assert_false(relpath.startswith('..'))
        assert_true(os.path.basename(file.path), file.b64id)

    def test_uploaded_file_content(self):
        file = UploadedFile.find_one(self.database)
        content = open(file.path).read()
        assert_equal(content, 'Content')


class TestInvalidJobSubmissionView:
    app: flask.Flask = None

    @classmethod
    def setup_class(cls):
        cls.app = load_app()
        os.makedirs(cls.app.config['uploads_dir'])
        cls.database = setup_database()
        with cls.app.test_client() as client:
            cls.response: flask.Response = client.post(
                "/api/services/fake/jobs",
                content_type="application/x-www-form-urlencoded",
                data={
                    'text-param': "Hello world",
                    'number-param': "alpha",
                }
            )

    @classmethod
    def teardown_class(cls):
        teardown_database()
        shutil.rmtree(cls.app.config['uploads_dir'])

    def test_status_code(self):
        assert_equal(self.response.status_code, 422)

    def test_errors(self):
        errors = self.response.get_json()['errors']
        assert_equal(len(errors), 1)
        error = errors[0]
        assert_dict_equal(
            error, {
                'parameter': "number-param",
                'errorCode': "invalid",
                'message': "Invalid decimal number"
            }
        )

    def test_no_reqeust_saved(self):
        request = JobRequest.find_one(self.database)
        assert_is_none(request)


class TestJobView:
    app: flask.Flask
    database: mongomock.Database
    request: JobRequest

    @classmethod
    def setup_class(cls):
        cls.app = load_app()

    def setup(self):
        self.database = setup_database()
        self.request = JobRequest(
            service="fake",
            inputs={"text-param": "foobar"}
        )
        insert_one(self.database, self.request)

    def test_status_code(self):
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{self.request.b64id}")
        assert_equal(response.status_code, 200)

    def test_alternative_route(self):
        with self.app.test_client() as client:
            response = client.get(f"/api/services/fake/jobs/{self.request.b64id}")
        assert_equal(response.status_code, 200)

    def test_resource_url(self):
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{self.request.b64id}")
        assert_equal(response.get_json()['@url'],
                     f"/api/jobs/{self.request.b64id}")

    def test_location_header(self):
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{self.request.b64id}")
        assert_equal(response.headers['Location'],
                     f'http://localhost/api/jobs/{self.request.b64id}')

    def test_id(self):
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{self.request.b64id}")
        assert_equal(response.get_json()['id'], self.request.b64id)

    def test_service(self):
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{self.request.b64id}")
        assert_equal(response.get_json()['service'], "fake")

    def test_parameters(self):
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{self.request.b64id}")
        assert_dict_equal(
            response.get_json()['parameters'], {'text-param': "foobar"}
        )

    def test_submission_time(self):
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{self.request.b64id}")
        assert_equal(response.get_json()['submissionTime'],
                     self.request.timestamp.strftime("%Y-%m-%dT%H:%M:%S"))

    def test_completion_time_is_none(self):
        with self.app.test_client() as client:
            response = client.get(f"api/jobs/{self.request.b64id}")
        assert_is_none(response.get_json()['completionTime'])

    def test_completion_time_present(self):
        self.request.status = JobStatus.COMPLETED
        self.request.completion_time = datetime(2021, 3, 21, 17, 35, 5)
        push_one(self.database, self.request)
        with self.app.test_client() as client:
            response = client.get(f"api/jobs/{self.request.b64id}")
        assert_equal(
            response.get_json()['completionTime'], "2021-03-21T17:35:05"
        )

    def test_not_finished(self):
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{self.request.b64id}")
        assert_false(response.get_json()['finished'])

    def test_finished(self):
        self.request.status = JobStatus.COMPLETED
        push_one(self.database, self.request)
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{self.request.b64id}")
        assert_true(response.get_json()['finished'])

    def test_all_statuses(self):
        for status in JobStatus:
            yield self._check_status_matching, status

    def _check_status_matching(self, status: JobStatus):
        self.request.status = status
        push_one(self.database, self.request)
        with self.app.test_client() as client:
            response = client.get(f'/api/jobs/{self.request.b64id}')
        assert_equal(response.get_json()['status'], status.name)

    def test_missing_job(self):
        with self.app.test_client() as client:
            response = client.get("/api/jobs/AADSHA1yHug3LAWY")
        assert_equal(response.status_code, 404)

    def test_invalid_job_id(self):
        with self.app.test_client() as client:
            response = client.get("/api/jobs/invalid-id")
        assert_equal(response.status_code, 404)


class TestJobFiles:
    app: flask.Flask
    database: mongomock.Database
    request0: JobRequest
    request1: JobRequest

    @classmethod
    def setup_class(cls):
        cls.app = load_app()
        jobs_dir = cls.app.config['jobs_dir']
        cls.database = setup_database()
        cls.request0 = JobRequest(
            service="fake", inputs={},
            job=dict(work_dir=os.path.join(jobs_dir, 'job-0'), job_id='0')
        )
        cls.request1 = JobRequest(
            service="fake", inputs={},
            job=dict(work_dir=os.path.join(jobs_dir, 'job-1'), job_id='1')
        )
        insert_many(cls.database, [cls.request0, cls.request1])

    @classmethod
    def teardown_class(cls):
        teardown_database()

    def test_list_files_response(self):
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{self.request0.b64id}/files")
        assert_equal(response.status_code, 200)
        assert_true(response.is_json)
        content = response.get_json()
        assert_in('files',  content)

    def test_files_list_job_0(self):
        jid = self.request0.b64id
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{jid}/files")
        files = response.get_json()['files']
        expected = [
            {
                '@url': f"/api/jobs/{jid}/files/stderr",
                '@content': f"/media/jobs/{jid}/stderr",
                'id': f"{jid}/stderr",
                'jobId': jid,
                'path': "stderr",
                'label': "Error log",
                'mediaType': "text/plain"
            }
        ]
        assert_list_equal(files, expected)

    def test_files_list_job_1(self):
        jid = self.request1.b64id
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{jid}/files")
        files = response.get_json()['files']
        expected = [
            {
                '@url': f"/api/jobs/{jid}/files/stderr",
                '@content': f"/media/jobs/{jid}/stderr",
                'id': f"{jid}/stderr",
                'jobId': jid,
                'path': "stderr",
                'label': "Error log",
                'mediaType': "text/plain"
            },
            {
                '@url': f"/api/jobs/{jid}/files/stdout",
                '@content': f"/media/jobs/{jid}/stdout",
                'id': f"{jid}/stdout",
                'jobId': jid,
                'path': "stdout",
                'label': "Standard output",
                'mediaType': "text/plain"
            },
            {
                '@url': f"/api/jobs/{jid}/files/dummy/d00.txt",
                '@content': f"/media/jobs/{jid}/dummy/d00.txt",
                'id': f"{jid}/dummy/d00.txt",
                'jobId': jid,
                'path': "dummy/d00.txt",
                'label': "Dummy files",
                'mediaType': "text/plain"
            },
            {
                '@url': f"/api/jobs/{jid}/files/dummy/d01.txt",
                '@content': f"/media/jobs/{jid}/dummy/d01.txt",
                'id': f"{jid}/dummy/d01.txt",
                'jobId': jid,
                'path': "dummy/d01.txt",
                'label': "Dummy files",
                'mediaType': "text/plain"
            }
        ]
        assert_equal(len(files), len(expected))
        for item1 in expected:
            for item2 in files:
                if item1['id'] == item2['id']:
                    assert_dict_equal(item1, item2)
                    break
            else:
                assert 0, f"item {item1} not found."

    def test_file_view_content(self):
        jid = self.request0.b64id
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{jid}/files/stderr")
        content = response.get_json()
        assert_dict_equal(content, {
            '@url': f"/api/jobs/{jid}/files/stderr",
            '@content': f"/media/jobs/{jid}/stderr",
            'id': f"{jid}/stderr",
            'jobId': jid,
            'path': "stderr",
            'label': "Error log",
            'mediaType': "text/plain"
        })

    def test_file_view_location_header(self):
        jid = self.request0.b64id
        with self.app.test_client() as client:
            response = client.get(f"/api/jobs/{jid}/files/stderr")
        assert_equal(
            response.headers['Location'],
            f"http://localhost/api/jobs/{jid}/files/stderr"
        )
