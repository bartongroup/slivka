import base64
import contextlib
import filecmp
import io
import os.path
import pathlib
import shutil
from base64 import urlsafe_b64decode
from datetime import datetime, timezone

import mongomock
import pytest
import yaml
from bson import ObjectId

import slivka.server
from slivka import JobStatus
from slivka.compat import resources
from slivka.conf import SlivkaSettings
from slivka.conf.loaders import load_settings_0_3
from slivka.db.documents import JobRequest, UploadedFile
from slivka.db.helpers import delete_one, insert_one, insert_many, delete_many, pull_one
from slivka.db.repositories import (
    ServiceStatusInfo,
    ServiceStatusMongoDBRepository,
)
from test.tools import in_any_order

resources_path = pathlib.Path(__file__).parent / "resources"


@pytest.fixture(scope="module")
def project_config(slivka_home) -> SlivkaSettings:
    template_path = os.path.join(os.path.dirname(__file__), "test_project")
    shutil.copytree(template_path, slivka_home, dirs_exist_ok=True)
    with open(os.path.join(slivka_home, "config.yml")) as config_file:
        config = load_settings_0_3(yaml.safe_load(config_file), slivka_home)
    return config


@pytest.fixture(scope="module")
def flask_app(project_config):
    os.environ["FLASK_DEBUG"] = "1"
    app = slivka.server.create_app(project_config)
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="module", autouse=True)
def uploads_directory(project_config: SlivkaSettings):
    path = project_config.directory.uploads
    os.makedirs(path, exist_ok=False)
    yield path
    shutil.rmtree(path)


@pytest.fixture(scope="module", autouse=True)
def jobs_directory(project_config: SlivkaSettings):
    path = project_config.directory.jobs
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
                "choices": ["alpha", "bravo", "charlie"],
            },
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
        "timestamp": datetime(2023, 8, 16, 12, 0).astimezone().isoformat(),
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
            "choice-param": "bravo",
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


# >>> Jobs listing tests >>>

@pytest.fixture()
def job_requests(request, database):
    data = yaml.safe_load(request.param)
    for req in data:
        oid = urlsafe_b64decode(req['_id'].encode())
        req['_id'] = ObjectId(oid)
    requests = [JobRequest(**it) for it in data]
    insert_many(database, requests)
    return requests


@pytest.mark.parametrize(
    "job_requests, query, expected_response",
    [
        (
            resources.open_text(__package__, 'resources/requests_set_1.yaml'),
            {"service": "test0"},
            {
                "totalCount": 4,
                "jobs": [
                    {
                        "@url": "/api/jobs/Z5oiTQoaTox_k8PF",
                        "id": "Z5oiTQoaTox_k8PF",
                        "service": "test0",
                        "parameters": {},
                        "submissionTime": datetime(2025, 1, 20, 20, 10, tzinfo=timezone.utc).astimezone().isoformat(),
                        "completionTime": None,
                        "finished": True,
                        "status": "FAILED"
                    },
                    {
                        "@url": "/api/jobs/Z5oiTQoaTox_k8PD",
                        "id": "Z5oiTQoaTox_k8PD",
                        "service": "test0",
                        "parameters": {},
                        "submissionTime": datetime(2025, 1, 20, 20, 0, tzinfo=timezone.utc).astimezone().isoformat(),
                        "completionTime": None,
                        "finished": True,
                        "status": "COMPLETED"
                    },
                    {
                        "@url": "/api/jobs/Z5oiTQoaTox_k8PC",
                        "id": "Z5oiTQoaTox_k8PC",
                        "service": "test0",
                        "parameters": {},
                        "submissionTime": datetime(2025, 1, 20, 19, 30, tzinfo=timezone.utc).astimezone().isoformat(),
                        "completionTime": None,
                        "finished": True,
                        "status": "COMPLETED"
                    },
                    {
                        "@url": "/api/jobs/Z5oiTQoaTox_k8PB",
                        "id": "Z5oiTQoaTox_k8PB",
                        "service": "test0",
                        "parameters": {},
                        "submissionTime": datetime(2025, 1, 20, 19, 0, tzinfo=timezone.utc).astimezone().isoformat(),
                        "completionTime": None,
                        "finished": True,
                        "status": "COMPLETED"
                    },
                ]
            }
        ),
        (
            resources.open_text(__package__, 'resources/requests_set_1.yaml'),
            {"service": "test1", "status": "FAILED"},
            {
                "totalCount": 1,
                "jobs": [
                    {
                        "@url": "/api/jobs/Z5oiTQoaTox_k8PE",
                        "id": "Z5oiTQoaTox_k8PE",
                        "service": "test1",
                        "parameters": {},
                        "submissionTime": datetime(2025, 1, 20, 20, 10, tzinfo=timezone.utc).astimezone().isoformat(),
                        "completionTime": None,
                        "finished": True,
                        "status": "FAILED"
                    }
                ]
            }
        )
    ],
    indirect=["job_requests"]
)
def test_list_jobs_with_filters(mongo_client, app_client, job_requests, query, expected_response):
    if isinstance(mongo_client, mongomock.MongoClient):
        pytest.skip("Unable to test with mongomock database")
    rep = app_client.get("/api/jobs/", query_string=query)
    assert rep.status_code == 200
    assert rep.json == expected_response


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
        expected = datetime(2023, 6, 18, tzinfo=timezone.utc) \
            .astimezone() \
            .isoformat()
        assert job_info["submissionTime"] == expected

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
def output_directory_factory(jobs_directory):
    created_dirs = []

    def make_dir(path):
        full_path = os.path.join(jobs_directory, *path.split("/"))
        os.makedirs(full_path)
        created_dirs.append(full_path)
        return full_path

    yield make_dir
    for path in created_dirs:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(
    scope="class",
    params=[
        (ObjectId("662a49a5f7e1108a2a260877"), "ZipJpffhEIoqJgh3"),
        (ObjectId("662a49a5f7e1108a2a260877"), "h3/Jg/ZipJpffhEIoq"),
        (ObjectId('6718f583e07eff184c688fdb'), "Zxj1g-B-_xhMaI_b"),
        (ObjectId('6718f583e07eff184c688fdb'), "_b/aI/Zxj1g-B-_xhM"),
        pytest.param(
            (ObjectId("662a49a5f7e1108a2a260877"), "ZipJ/pffh/EIoq/Jgh3"),
            marks=[pytest.mark.xfail(reason="current format has parts backwards")]
        ),
        pytest.param(
            (ObjectId("662a49a5f7e1108a2a260877"), "AsfTSbcDEIoqJgh3"),
            marks=[pytest.mark.xfail(reason="arbitrary paths not supported")],
        ),
        pytest.param(
            (ObjectId("662a49a5f7e1108a2a260877"), "arbitrary/dir"),
            marks=[pytest.mark.xfail(reason="arbitrary paths not supported")]
        ),
    ],
)
def completed_job_request(request, database, output_directory_factory):
    oid = request.param[0]
    path = output_directory_factory(request.param[1])
    job_request = JobRequest(
        _id=oid,
        service="fake",
        inputs={},
        timestamp=datetime(2022, 6, 11, 8, 50),
        completion_time=datetime(2022, 6, 11, 8, 54),
        status=JobStatus.COMPLETED,
        runner="default",
        job={"work_dir": path, "job_id": 0},
    )
    insert_one(database, job_request)
    yield job_request
    delete_one(database, job_request)


@pytest.fixture(scope="class")
def outputs_view_response(app_client, job_request_id):
    return app_client.get(f"/api/jobs/{job_request_id}/files")


@pytest.fixture(scope="class")
def outputs_info(outputs_view_response):
    return outputs_view_response.get_json()


class TestOutputsIfCompleteResults:
    @pytest.fixture(scope="class", autouse=True)
    def job_request_id(self, database, completed_job_request):
        out_path = pathlib.Path(completed_job_request.job.cwd)
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
        return completed_job_request.b64id

    def test_files_list(
        self, completed_job_request, outputs_info, jobs_directory
    ):
        job_request_id = completed_job_request.b64id
        output_path = os.path.relpath(
            completed_job_request.job.cwd, jobs_directory
        )
        assert outputs_info["files"] == in_any_order(
            {
                "@url": f"/api/jobs/{job_request_id}/files/stdout",
                "@content": f"/media/jobs/{output_path}/stdout",
                "id": f"{job_request_id}/stdout",
                "jobId": job_request_id,
                "path": "stdout",
                "label": "Standard output",
                "mediaType": "text/plain",
            },
            {
                "@url": f"/api/jobs/{job_request_id}/files/stderr",
                "@content": f"/media/jobs/{output_path}/stderr",
                "id": f"{job_request_id}/stderr",
                "jobId": job_request_id,
                "path": "stderr",
                "label": "Error log",
                "mediaType": "text/plain",
            },
            {
                "@url": f"/api/jobs/{job_request_id}/files/dummy/d00.txt",
                "@content": f"/media/jobs/{output_path}/dummy/d00.txt",
                "id": f"{job_request_id}/dummy/d00.txt",
                "jobId": job_request_id,
                "path": "dummy/d00.txt",
                "label": "Dummy files",
                "mediaType": "text/plain",
            },
            {
                "@url": f"/api/jobs/{job_request_id}/files/dummy/d01.txt",
                "@content": f"/media/jobs/{output_path}/dummy/d01.txt",
                "id": f"{job_request_id}/dummy/d01.txt",
                "jobId": job_request_id,
                "path": "dummy/d01.txt",
                "label": "Dummy files",
                "mediaType": "text/plain",
            },
            {
                "@url": f"/api/jobs/{job_request_id}/files/dummy/d02.txt",
                "@content": f"/media/jobs/{output_path}/dummy/d02.txt",
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
    @pytest.fixture(scope="class", autouse=True)
    def create_job_files(self, database, completed_job_request):
        out_path = pathlib.Path(completed_job_request.job.cwd)
        with open(out_path / "stderr", "w") as f:
            print("ERROR: failed", file=f)

    @pytest.fixture(scope="class")
    def job_request_id(self, completed_job_request):
        return completed_job_request.b64id

    def test_files_list(
        self, completed_job_request, jobs_directory, outputs_info
    ):
        job_request = completed_job_request
        job_request_id = completed_job_request.b64id
        output_path = os.path.relpath(job_request.job.cwd, jobs_directory)
        assert outputs_info["files"] == in_any_order(
            {
                "@url": f"/api/jobs/{job_request_id}/files/stderr",
                "@content": f"/media/jobs/{output_path}/stderr",
                "id": f"{job_request_id}/stderr",
                "jobId": job_request_id,
                "path": "stderr",
                "label": "Error log",
                "mediaType": "text/plain",
            },
        )


class TestOutputsIfJobNotInitialized:
    @pytest.fixture(scope="class")
    def job_request_id(self, database):
        job_request = JobRequest(service="fake", inputs={})
        insert_one(database, job_request)
        yield job_request.b64id
        delete_one(database, job_request)

    def test_files_list(self, job_request_id, outputs_info):
        assert outputs_info["files"] == []


class TestOutputFileView:
    @pytest.fixture()
    def view_response(self, app_client, completed_job_request):
        with open(
            os.path.join(completed_job_request.job.cwd, "stderr"), "w"
        ) as f:
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

    def test_file_info(self, completed_job_request, file_info, jobs_directory):
        output_path = os.path.relpath(
            completed_job_request.job.cwd, jobs_directory
        )
        job_id = completed_job_request.b64id
        assert file_info == {
            "@url": f"/api/jobs/{job_id}/files/stderr",
            "@content": f"/media/jobs/{output_path}/stderr",
            "id": f"{job_id}/stderr",
            "jobId": job_id,
            "path": "stderr",
            "label": "Error log",
            "mediaType": "text/plain",
        }

    def test_file_content(self, app_client, file_info):
        rep = app_client.get(file_info["@content"])
        assert rep.text == "ERROR: failed\n"


def test_job_view_parameters_output_used_as_input(
    app_client, completed_job_request
):
    with open(os.path.join(completed_job_request.job.cwd, "stdout"), "w") as f:
        print(file=f)
    response = app_client.post(
        "/api/services/fake/jobs",
        data={
            "text-param": "Hello world",
            "file-param": f"{completed_job_request.b64id}/stdout",
        },
    )
    assert (
        response.json["parameters"]["file-param"]
        == f"{completed_job_request.b64id}/stdout"
    )


class TestSuccessfulFileUpload:
    @pytest.fixture(scope="class")
    def response(self, app_client):
        return app_client.post(
            "/api/files",
            data={"file": (
                resources.open_binary(__package__, "resources/example.txt"),
                "example file",
                "application/x-lipsum"
            )}
        )

    def test_status_201(self, response):
        assert response.status_code == 201

    def test_file_has_title(self, response):
        assert response.json["label"] == "example file"

    def test_file_has_media_type(self, response):
        assert response.json["mediaType"] == "application/x-lipsum"

    def test_file_exists_in_uploads(self, response, uploads_directory):
        uploaded_file_path = os.path.join(uploads_directory, response.json['path'])
        assert os.path.exists(uploaded_file_path)
        assert filecmp.cmp(resources_path / "example.txt", uploaded_file_path)


def test_file_upload_missing_file_parameter(app_client):
    response = app_client.post(
        "/api/files",
        data={"input": resources.open_binary(__package__, "resources/example.txt")}
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    ("title", "content_type", "expected_title", "expected_media_type"),
    [
        ("Title", "application/x-lorem", "Title", "application/x-lorem"),
        ("Other Title", "text/plain; charset=UTF-8", "Other Title", "text/plain")
    ]
)
class TestUploadJobInput:
    @pytest.fixture()
    def input_file_id(self, app_client, title, content_type):
        response = app_client.post(
            "/api/services/fake/jobs",
            data={
                "text-param": "some text",
                "file-param": (
                    resources.open_binary(__package__, "resources/example.txt"),
                    title,
                    content_type
                )
            }
        )
        assert response.status_code == 202
        return response.json["parameters"]["file-param"]

    @pytest.fixture()
    def file_response(self, app_client, input_file_id):
        return app_client.get(f"/api/files/{input_file_id}")

    def test_file_exists(self, file_response, expected_title, expected_media_type):
        assert file_response.status_code == 200

    def test_file_has_label(self, file_response, expected_title, expected_media_type):
        assert file_response.json["label"] == expected_title

    def test_file_has_media_type(self, file_response, expected_title, expected_media_type):
        assert file_response.json["mediaType"] == expected_media_type

    def test_file_has_no_job(self, file_response, expected_title, expected_media_type):
        assert file_response.json["jobId"] is None

    def test_file_exists_in_uploads(self, uploads_directory, file_response, expected_title, expected_media_type):
        uploaded_file_path = os.path.join(uploads_directory, file_response.json['path'])
        assert os.path.exists(uploaded_file_path)
        assert filecmp.cmp(resources_path / "example.txt", uploaded_file_path)


@pytest.fixture(scope="class")
def add_uploaded_file(uploads_directory, database):
    added_paths = []
    added_files = []
    def add_file(file, title=None, media_type=None):
        nonlocal added_paths, added_files
        oid = ObjectId()
        filename = base64.urlsafe_b64encode(oid.binary).decode()
        path = os.path.join(uploads_directory, filename)
        with open(path, "w") as fdst:
            shutil.copyfileobj(file, fdst)
        added_paths.append(path)
        uploaded_file = UploadedFile(_id=oid, title=title, media_type=media_type, path=path)
        insert_one(database, uploaded_file)
        added_files.append(uploaded_file)
        return uploaded_file
    yield add_file
    for path in added_paths:
        with contextlib.suppress(IOError):
            os.remove(path)
    delete_many(database, added_files)


@pytest.mark.parametrize(
    "new_data, expected_data",
    [
        (
            {},
            {"label": "initial title", "mediaType": "text/initial-type"}
        ),
        (
            {"label": "new title"},
            {"label": "new title", "mediaType": "text/initial-type"}
        ),
        (
            {"mediaType": "text/lorem"},
            {"label": "initial title", "mediaType": "text/lorem"}
        ),
        (
            {"label": "another title", "mediaType": "text/lipsum"},
            {"label": "another title", "mediaType": "text/lipsum"}
        )
    ]
)
def test_update_file_metadata(app_client, database, add_uploaded_file, new_data, expected_data):
    uploaded_file = add_uploaded_file(
        resources.open_text(__package__, "resources/example.txt"),
        title="initial title",
        media_type="text/initial-type"
    )
    reply = app_client.put(f"/api/files/{uploaded_file.b64id}", data=new_data)
    pull_one(database, uploaded_file)
    assert reply.status_code == 200
    assert reply.json["label"] == expected_data["label"]
    assert reply.json["mediaType"] == expected_data["mediaType"]

    assert uploaded_file.title == expected_data["label"]
    assert uploaded_file.media_type == expected_data["mediaType"]
