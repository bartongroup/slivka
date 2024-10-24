import shutil
from importlib import resources

import pytest
import yaml
from bson import ObjectId

import slivka.migrations.migration_1


@pytest.fixture(autouse=True)
def project_files(slivka_home):
    traversable = resources.files(__package__) / '0.8.5-flat-directory-project'
    with resources.as_file(traversable) as path:
        shutil.copytree(path, slivka_home, dirs_exist_ok=True)


@pytest.fixture()
def job_requests(slivka_home, database):
    resource_location = (
            resources.files(__package__) /
            '0.8.5-flat-directory-project' /
            'mongodb-requests.yaml')
    requests = yaml.load(resource_location.open('r'), Loader=yaml.SafeLoader)
    for item in requests:
        item['_id'] = ObjectId(item['_id'])
        item['job']['work_dir'] = str(slivka_home / "jobs" / item['job']['work_dir'])
    return database['requests'].insert_many(requests)


# WARNING! slivka_home has module scope. multiple tests may conflict
def test_directory_migration(slivka_home, database, job_requests):
    slivka.migrations.migration_1.apply()
    requests = list(database['requests'].find(
        {'_id': {"$in": job_requests.inserted_ids}}
    ))
    expected_wds = [
        str(slivka_home / "jobs" / item)
        for item in ["2B/-y/ZmLspcnTMnyl", "2C/-y/ZmLwrcnTMnyl"]
    ]
    for request, expected_wd in zip(requests, expected_wds):
        assert request['job']['work_dir'] == expected_wd
        assert (slivka_home / "jobs" / expected_wd).is_dir()
