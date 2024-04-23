import os
import shutil
from random import randint
from unittest import mock

import mongomock
import pytest

import slivka.db
from slivka.compat.resources import open_binary


@pytest.fixture(scope="package")
def mongo_client():
    slivka.db.mongo = mongomock.MongoClient()
    with slivka.db.mongo as client:
        yield client
    del slivka.db.mongo


@pytest.fixture(scope="class", autouse=True)
def database(mongo_client):
    slivka.db.database = mongo_client.slivkadb
    yield slivka.db.database
    for collection_name in slivka.db.database.list_collection_names():
        slivka.db.database.drop_collection(collection_name)
    del slivka.db.database


@pytest.fixture(scope="module", autouse=True)
def slivka_home(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("slivka-home")
    with mock.patch.dict(os.environ, SLIVKA_HOME=str(tmp_path)):
        yield tmp_path


@pytest.fixture()
def job_directory(slivka_home):
    (slivka_home / "jobs").mkdir(exist_ok=True)
    max_uint16 = (1 << 16) - 1
    path = (slivka_home / "jobs"
            / f"{randint(0, max_uint16):04x}"
            / f"{randint(0, max_uint16):04x}")
    yield str(path)
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def job_directory_factory(slivka_home):
    (slivka_home / "jobs").mkdir(exist_ok=True)
    generated_paths = []

    def path_factory():
        nonlocal generated_paths
        max_uint16 = (1 << 16) - 1
        job_path = (slivka_home / "jobs"
                    / f"{randint(0, max_uint16):04x}"
                    / f"{randint(0, max_uint16):04x}")
        generated_paths.append(job_path)
        return str(job_path)

    yield path_factory
    for path in generated_paths:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(scope="function")
def minimal_project(slivka_home):
    in_stream = open_binary("test", "resources/minimal_project/settings.yaml")
    with open(slivka_home / "settings.yaml", "wb") as out_file:
        shutil.copyfileobj(in_stream, out_file)
