import io
import os.path
import pathlib
import shutil
import tempfile
from datetime import datetime

import pytest
import yaml

import slivka.compat.resources
import slivka.server
from test.tools import in_any_order
from slivka import JobStatus
from slivka.conf.loaders import load_settings_0_3
from slivka.db.documents import UploadedFile, JobRequest
from slivka.db.helpers import insert_one, delete_one
from slivka.db.repositories import ServiceStatusInfo, ServiceStatusMongoDBRepository

project_path = os.path.join(os.path.dirname(__file__), "test_project")


@pytest.fixture(scope="module")
def flask_app():
    os.environ["FLASK_DEBUG"] = "1"
    with open(os.path.join(project_path, "config.yml")) as config_file:
        config = load_settings_0_3(yaml.safe_load(config_file), project_path)
    app = slivka.server.create_app(config)
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="module", autouse=True)
def uploads_directory(flask_app):
    path = flask_app.config["uploads_dir"]
    os.makedirs(path, exist_ok=False)
    yield path
    shutil.rmtree(path)


@pytest.fixture(scope="module", autouse=True)
def jobs_directory(flask_app):
    path = flask_app.config["jobs_dir"]
    os.makedirs(path, exist_ok=False)
    yield path
    shutil.rmtree(path)


@pytest.fixture(scope="module")
def app_client(flask_app):
    with flask_app.test_client() as client:
        yield client


def test_version_view(app_client):
    rep = app_client.get("/api/version")
    assert rep.status_code == 200
    assert rep.get_json() == {
        "slivkaVersion": slivka.__version__,
        "APIVersion": "1.1",
    }


def test_services_list_view(app_client):
    rep = app_client.get("/api/services")
    assert rep.status_code == 200
    rep = rep.get_json()
    assert "services" in rep
    assert len(rep["services"]) == 1


class TestFakeServiceView:
    @pytest.fixture(scope="class")
    def service_info(self, app_client):
        rep = app_client.get("/api/services/fake")
        assert rep.status_code == 200
        return rep.get_json()

    def test_service_url(self, service_info):
        assert service_info["@url"] == "/api/services/fake"

    def test_service_id(self, service_info):
        assert service_info["id"] == "fake"

    def test_service_name(self, service_info):
        assert service_info["name"] == "Fake service"

    def test_service_description(self, service_info):
        assert service_info["description"] == "Description of fake service"

    def test_service_author(self, service_info):
        assert service_info["author"] == "John Smith"

    def test_service_version(self, service_info):
        assert service_info["version"] == "0.6.7"

    def test_service_license(self, service_info):
        assert service_info["license"] == "Dummy License"

    def test_service_classifiers(self, service_info):
        assert service_info["classifiers"] == ["Class::Test", "Group::Dummy"]

    def test_service_default_status(self, service_info):
        assert service_info["status"] == {
            "status": "UNKNOWN",
            "errorMessage": "",
            "timestamp": datetime.fromtimestamp(0).isoformat(),
        }

    def test_service_parameters(self, service_info):
        assert service_info["parameters"] == [
            {
                "type": "file",
                "id": "file-param",
                "name": "File parameter",
                "description": "Input file",
                "required": False,
                "array": False,
                "default": None,
            },
            {
                "type": "text",
                "id": "text-param",
                "name": "Text parameter",
                "description": "Description of text parameter",
                "required": True,
                "array": False,
                "default": None,
            },
            {
                "type": "decimal",
                "id": "number-param",
                "name": "Number parameter",
                "description": "Description of number parameter",
                "required": False,
                "array": False,
                "default": 0.1,
            },
            {
                "type": "choice",
                "id": "choice-param",
                "name": "Choice parameter",
                "description": "Description of choice parameter",
                "required": False,
                "default": None,
                "array": False,
                "choices": ["alpha", "bravo", "charlie"]
            }
        ]


@pytest.fixture()
def service_status_repository(database):
    return ServiceStatusMongoDBRepository(database)


@pytest.fixture(
    params=[
        (ServiceStatusInfo.OK, "OK"),
        (ServiceStatusInfo.WARNING, "Executor overloaded"),
        (ServiceStatusInfo.DOWN, "Critical error"),
    ]
)
def service_state(request, service_status_repository):
    status, message = request.param
    status_entry = ServiceStatusInfo(
        service="fake",
        runner="default",
        status=status,
        message=message,
        timestamp=datetime(2023, 8, 16, 12, 0),
    )
    service_status_repository.insert(status_entry)
    return status, message


def test_service_view_state_info(app_client, service_state):
    state, message = service_state
    rep = app_client.get("/api/services/fake")
    assert rep.status_code == 200
    service_info = rep.get_json()
    assert service_info["status"] == {
        "status": state.name,
        "errorMessage": message,
        "timestamp": "2023-08-16T12:00:00",
    }


def test_service_view_missing_service(app_client):
    rep = app_client.get("/api/services/nonexistent")
    assert rep.status_code == 404


class TestJobCreatedView:
    @pytest.fixture(scope="class")
    def server_response(self, app_client):
        return app_client.post(
            "/api/services/fake/jobs",
            content_type="multipart/form-data",
            data={
                "text-param": "Hello world",
                "number-param": 12.3,
                "file-param": (io.BytesIO(b"Content"), "input file"),
                "choice-param": "bravo",
            },
        )

    @pytest.fixture(scope="class")
    def job_info(self, server_response):
        assert 200 <= server_response.status_code < 300
        return server_response.get_json()

    def test_status_code(self, server_response):
        assert server_response.status_code == 202  # CREATED

    def test_job_url(self, job_info):
        uid = job_info["id"]
        assert job_info["@url"] == f"/api/jobs/{uid}"

    def test_location_header(self, server_response, job_info):
        uid = job_info["id"]
        assert server_response.headers["Location"] == f"/api/jobs/{uid}"

    def test_job_service(self, job_info):
        assert job_info["service"] == "fake"

    def test_job_status(self, job_info):
        assert job_info["status"] == "PENDING"

    def test_job_parameters(self, database, job_info):
        file = UploadedFile.find_one(database)
        assert job_info["parameters"] == {
            "text-param": "Hello world",
            "number-param": "12.3",
            "file-param": file.b64id,
            "choice-param": "bravo"
        }

    @pytest.fixture(scope="class")
    def job_request(self, database, job_info):
        return JobRequest.find_one(database, id=job_info["id"])

    @pytest.fixture(scope="class")
    def uploaded_file(self, database, job_info):
        return UploadedFile.find_one(
            database, id=job_info["parameters"]["file-param"]
        )

    def test_job_request_uid(self, job_info, job_request):
        assert job_request.b64id == job_info["id"]

    def test_job_request_service(self, job_request):
        assert job_request.service == "fake"

    def test_job_request_inputs(self, job_request, uploaded_file):
        assert job_request.inputs == {
            "text-param": "Hello world",
            "number-param": "12.3",
            "file-param": uploaded_file.path,
            "choice-param": "B",
        }

    def test_uploaded_file_content(self, uploaded_file):
        assert open(uploaded_file.path).read() == "Content"


class TestJobInvalidView:
    @pytest.fixture(scope="class")
    def server_response(self, app_client):
        return app_client.post(
            "/api/services/fake/jobs",
            content_type="multipart/form-data",
            data={
                "text-param": "Hello world",
                "number-param": "not-a-number",
            },
        )

    @pytest.fixture(scope="class")
    def job_info(self, server_response):
        return server_response.get_json()

    def test_status_code(self, server_response):
        assert server_response.status_code == 422

    def test_info_errors(self, job_info):
        errors = job_info["errors"]
        assert len(errors) == 1
        assert errors[0] == {
            "parameter": "number-param",
            "errorCode": "invalid",
            "message": "Invalid decimal number",
        }

    def test_no_job_request_created(self, database):
        assert JobRequest.find_one(database) is None


@pytest.fixture(
    scope="class", params=["/api/jobs/%s", "/api/services/fake/jobs/%s"]
)
def job_view_response(request, app_client, job_request_id):
    url = request.param % job_request_id
    return app_client.get(url)


@pytest.fixture(scope="class")
def job_info(job_view_response):
    return job_view_response.get_json()


class TestJobViewForExistingJob:
    @pytest.fixture(scope="class")
    def job_request(self, database):
        request = JobRequest(
            service="fake",
            inputs={
                "text-param": "foobar",
                "number-param": "3.1415",
                "choice-param": "C",
            },
            timestamp=datetime(2023, 6, 18),
        )
        insert_one(database, request)
        yield request
        delete_one(database, request)

    @pytest.fixture(scope="class")
    def job_request_id(self, job_request):
        return job_request.b64id

    def test_status_code(self, job_view_response):
        assert job_view_response.status_code == 200

    def test_resource_url(self, job_request_id, job_info):
        assert job_info["@url"] == f"/api/jobs/{job_request_id}"

    def test_location_header(self, job_request_id, job_view_response):
        assert (
            job_view_response.headers["Location"]
            == f"/api/jobs/{job_request_id}"
        )

    def test_job_id(self, job_request_id, job_info):
        assert job_info["id"] == job_request_id

    def test_job_service(self, job_info):
        assert job_info["service"] == "fake"

    def test_job_parameters(self, job_info):
        assert job_info["parameters"] == {
            "text-param": "foobar",
            "number-param": "3.1415",
            "choice-param": "charlie",
        }

    def test_job_submission_time(self, job_info):
        assert job_info["submissionTime"] == "2023-06-18T00:00:00"

    def test_job_completion_time_is_none(self, job_info):
        assert job_info.get("completionTime") is None

    def test_job_is_not_finished(self, job_info):
        assert not job_info["finished"]

    def test_job_status_is_pending(self, job_info):
        assert job_info["status"] == "PENDING"


class TestJobViewForNonExistingJob:
    @pytest.fixture(scope="class", params=["AADSHA1yHug3LAWY", "invalid"])
    def job_request_id(self, request):
        return request.param

    def test_status_code(self, job_view_response):
        assert job_view_response.status_code == 404


class TestJobViewStatus:
    @pytest.fixture(scope="class", params=list(JobStatus))
    def job_status(self, request):
        return request.param

    @pytest.fixture(scope="class")
    def job_request(self, database, job_status):
        request = JobRequest(
            service="fake",
            inputs={"text-param": "foobar"},
            timestamp=datetime(2023, 6, 18),
            status=job_status,
        )
        insert_one(database, request)
        yield request
        delete_one(database, request)

    @pytest.fixture(scope="class")
    def job_request_id(self, job_request):
        return job_request.b64id

    def test_job_status(self, job_info, job_status):
        assert job_info["status"] == job_status.name

    def test_job_finished(self, job_info, job_status):
        assert job_info["finished"] == job_status.is_finished()


@pytest.fixture(scope="class")
def output_directory(flask_app, jobs_directory):
    jobs_dir = tempfile.TemporaryDirectory(dir=jobs_directory)
    with jobs_dir as path:
        yield path


@pytest.fixture(scope="class")
def outputs_view_response(app_client, job_request_id):
    return app_client.get(f"/api/jobs/{job_request_id}/files")


@pytest.fixture(scope="class")
def outputs_info(outputs_view_response):
    return outputs_view_response.get_json()


class TestOutputsIfCompleteResults:
    @pytest.fixture(scope="class")
    def job_request_id(self, database, output_directory):
        job_request = JobRequest(
            service="fake",
            inputs={},
            job={"work_dir": output_directory, "job_id": 0},
        )

        out_path = pathlib.Path(output_directory)
        with open(out_path / "stdout", "w") as f:
            print("Hello world", file=f)
        with open(out_path / "stderr", "w") as f:
            print("INFO: successful", file=f)
        dummy_out_path = out_path / "dummy"
        dummy_out_path.mkdir()
        (dummy_out_path / "d00.txt").touch()
        (dummy_out_path / "d01.txt").touch()
        (dummy_out_path / "d02.txt").touch()
        (dummy_out_path / "d00.md").touch()
        (dummy_out_path / "f00.txt").touch()

        insert_one(database, job_request)
        yield job_request.b64id
        delete_one(database, job_request)

    def test_files_list(self, job_request_id, outputs_info):
        assert outputs_info["files"] == in_any_order(
            {
                "@url": f"/api/jobs/{job_request_id}/files/stdout",
                "@content": f"/media/jobs/{job_request_id}/stdout",
                "id": f"{job_request_id}/stdout",
                "jobId": job_request_id,
                "path": "stdout",
                "label": "Standard output",
                "mediaType": "text/plain",
            },
            {
                "@url": f"/api/jobs/{job_request_id}/files/stderr",
                "@content": f"/media/jobs/{job_request_id}/stderr",
                "id": f"{job_request_id}/stderr",
                "jobId": job_request_id,
                "path": "stderr",
                "label": "Error log",
                "mediaType": "text/plain",
            },
            {
                "@url": f"/api/jobs/{job_request_id}/files/dummy/d00.txt",
                "@content": f"/media/jobs/{job_request_id}/dummy/d00.txt",
                "id": f"{job_request_id}/dummy/d00.txt",
                "jobId": job_request_id,
                "path": "dummy/d00.txt",
                "label": "Dummy files",
                "mediaType": "text/plain",
            },
            {
                "@url": f"/api/jobs/{job_request_id}/files/dummy/d01.txt",
                "@content": f"/media/jobs/{job_request_id}/dummy/d01.txt",
                "id": f"{job_request_id}/dummy/d01.txt",
                "jobId": job_request_id,
                "path": "dummy/d01.txt",
                "label": "Dummy files",
                "mediaType": "text/plain",
            },
            {
                "@url": f"/api/jobs/{job_request_id}/files/dummy/d02.txt",
                "@content": f"/media/jobs/{job_request_id}/dummy/d02.txt",
                "id": f"{job_request_id}/dummy/d02.txt",
                "jobId": job_request_id,
                "path": "dummy/d02.txt",
                "label": "Dummy files",
                "mediaType": "text/plain",
            },
        )

    def test_response_status_code(self, outputs_view_response):
        assert outputs_view_response.status_code == 200


class TestOutputsIfIncompleteResult:
    @pytest.fixture(scope="class")
    def job_request_id(self, database, output_directory):
        job_request = JobRequest(
            service="fake",
            inputs={},
            job={"work_dir": output_directory, "job_id": 0},
        )
        out_path = pathlib.Path(output_directory)
        with open(out_path / "stderr", "w") as f:
            print("ERROR: failed", file=f)
        insert_one(database, job_request)
        yield job_request.b64id
        delete_one(database, job_request)

    def test_files_list(self, job_request_id, outputs_info):
        assert outputs_info["files"] == in_any_order(
            {
                "@url": f"/api/jobs/{job_request_id}/files/stderr",
                "@content": f"/media/jobs/{job_request_id}/stderr",
                "id": f"{job_request_id}/stderr",
                "jobId": job_request_id,
                "path": "stderr",
                "label": "Error log",
                "mediaType": "text/plain",
            },
        )


class TestOutputsIfJobNotInitialized:
    @pytest.fixture(scope="class")
    def job_request_id(self, database, output_directory):
        job_request = JobRequest(
            service="fake",
            inputs={}
        )
        insert_one(database, job_request)
        yield job_request.b64id
        delete_one(database, job_request)

    def test_files_list(self, job_request_id, outputs_info):
        assert outputs_info["files"] == []


@pytest.fixture()
def completed_job_request(database, output_directory):
    job_request = JobRequest(
        service="fake",
        inputs={},
        timestamp=datetime(2022, 6, 11, 8, 50),
        completion_time=datetime(2022, 6, 11, 8, 54),
        status=JobStatus.COMPLETED,
        runner="default",
        job={"work_dir": output_directory, "job_id": 0},
    )
    insert_one(database, job_request)
    yield job_request
    delete_one(database, job_request)


class TestOutputFileView:
    @pytest.fixture()
    def view_response(
        self, app_client, completed_job_request, output_directory
    ):
        with open(os.path.join(output_directory, "stderr"), "w") as f:
            print("ERROR: failed", file=f)
        job_id = completed_job_request.b64id
        return app_client.get(f"/api/jobs/{job_id}/files/stderr")

    @pytest.fixture()
    def file_info(self, view_response):
        return view_response.get_json()

    def test_response_location_header(
        self, completed_job_request, view_response
    ):
        job_id = completed_job_request.b64id
        assert (
            view_response.headers["Location"]
            == f"/api/jobs/{job_id}/files/stderr"
        )

    def test_response_status_code(self, view_response):
        assert view_response.status_code == 200

    def test_file_info(self, completed_job_request, file_info):
        job_id = completed_job_request.b64id
        assert file_info == {
            "@url": f"/api/jobs/{job_id}/files/stderr",
            "@content": f"/media/jobs/{job_id}/stderr",
            "id": f"{job_id}/stderr",
            "jobId": job_id,
            "path": "stderr",
            "label": "Error log",
            "mediaType": "text/plain",
        }

    @pytest.mark.xfail(
        reason="current implementation requires directory name match job request id"
    )
    def test_file_content(self, app_client, file_info):
        rep = app_client.get(file_info["@content"])
        assert rep.text == "ERROR: failed\n"
