import pytest
import mongomock
import slivka.db


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
