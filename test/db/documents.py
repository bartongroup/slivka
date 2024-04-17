import datetime

import pytest
from bson import ObjectId

from slivka.utils import JobStatus
from slivka.db.documents import JobRequest, MongoDocument


def test_mongo_document_to_dict_empty_doc():
    doc = MongoDocument()
    assert dict(doc) == {}


def test_mongo_document_to_dict_with_id():
    object_id = ObjectId()
    doc = MongoDocument(_id=object_id)
    assert dict(doc) == {"_id": object_id}


def test_mongo_document_contains_existing_key():
    doc = MongoDocument(_id=ObjectId())
    assert "_id" in doc


@pytest.mark.parametrize("key", ["_id", "undefined", None, 1])
def test_mongo_document_contains_missing_key(key):
    doc = MongoDocument()
    assert key not in doc


def test_mongo_document_getitem_existing_key():
    doc = MongoDocument(_id=ObjectId())
    assert doc["_id"]


@pytest.mark.parametrize("key", ["_id", "undefined", None, 1])
def test_mongo_document_getitem_missing_key(key):
    doc = MongoDocument()
    with pytest.raises(KeyError):
        assert doc[key]


def test_job_request_to_dict():
    job = JobRequest(
        service="example",
        inputs={},
        timestamp=datetime.datetime(2024, 4, 12),
        runner="default",
    )
    assert dict(job) == {
        "service": "example",
        "inputs": {},
        "timestamp": datetime.datetime(2024, 4, 12),
        "runner": "default",
        "status": 1,
        "completion_time": None,
        "job": None,
    }


@pytest.mark.parametrize(
    "key", ["service", "inputs", "timestamp", "runner", "status"]
)
def test_job_request_contains_existing_properties(key):
    job = JobRequest(
        service="example",
        inputs={},
        timestamp=datetime.datetime(2024, 4, 12),
        runner="default",
    )
    assert key in job


def test_job_request_iter_id_not_present():
    job = JobRequest(
        service="example",
        inputs={},
        timestamp=datetime.datetime(2024, 4, 12),
        runner="default",
        status=JobStatus.PENDING,
        completion_time=None,
        job=None,
    )
    assert set(iter(job)) == {
        "service",
        "inputs",
        "timestamp",
        "runner",
        "status",
        "completion_time",
        "job",
    }


def test_job_request_iter_id_present():
    job = JobRequest(
        _id=ObjectId(),
        service="example",
        inputs={},
        timestamp=datetime.datetime(2024, 4, 12),
        runner="default",
        status=2
    )
    assert set(iter(job)) == {
        "_id",
        "service",
        "inputs",
        "timestamp",
        "runner",
        "status",
        "completion_time",
        "job"
    }


def test_job_request_job_converter_from_job_object():
    job = JobRequest.Job(work_dir="/tmp", job_id='0')
    req = JobRequest(
        service="example",
        inputs={},
        job=job
    )
    assert isinstance(req.job, JobRequest.Job)


def test_job_request_job_converter_from_dict():
    job = {"work_dir": "/tmp", "job_id": "0"}
    req = JobRequest(
        service="example",
        inputs={},
        job=job
    )
    assert isinstance(req.job, JobRequest.Job)


def test_job_request_insert_id_not_present(database):
    job = JobRequest(service="example", inputs={})
    collection = database["job-request"]
    collection.insert_one(job)
    assert isinstance(job._id, ObjectId)


def test_job_request_insert_id_present(database):
    object_id = ObjectId()
    job = JobRequest(_id=object_id, service="example", inputs={})
    collection = database["job-request"]
    collection.insert_one(job)
    assert job._id == object_id
