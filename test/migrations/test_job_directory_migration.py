import os
import shutil
from importlib import resources

import pytest
import yaml
from bson import ObjectId

import slivka.migrations.migration_1


@pytest.fixture(scope="class")
def project_files(request, slivka_home):
    traversable = request.param
    with resources.as_file(traversable) as path:
        shutil.copytree(path, slivka_home, dirs_exist_ok=True)


@pytest.fixture(scope="class")
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



@pytest.mark.parametrize(
    'project_files',
    [
        resources.files(__package__) / '0.8.5-flat-directory-project',
    ],
    indirect=['project_files']
)
@pytest.mark.usefixtures('job_requests')
class TestApplyMigration:
    @pytest.fixture(scope="class", autouse=True)
    def run_migration(self, slivka_home, database):
        slivka.migrations.migration_1.apply(database, str(slivka_home / "jobs"))

    def test_directory_moved(self, slivka_home):
        assert (slivka_home / "jobs" / "AA" / "AA" / "AAAAAAAAAAAA").is_dir()
        assert (slivka_home / "jobs" / "AB" / "AA" / "AAAAAAAAAAAA").is_dir()

    def test_files_moved(self, slivka_home):
        assert (slivka_home / "jobs" / "AA" / "AA" / "AAAAAAAAAAAA" / "stdout").is_file()
        assert (slivka_home / "jobs" / "AB" / "AA" / "AAAAAAAAAAAA" / "stdout").is_file()

    def test_work_dir_updated(self, database, slivka_home, job_requests):
        request_0 = database['requests'].find_one({'_id': ObjectId('000000000000000000000000')})
        assert request_0['job']['work_dir'] == str(slivka_home / 'jobs' / 'AA' / 'AA' / 'AAAAAAAAAAAA')
        request_1 = database['requests'].find_one({'_id': ObjectId('000000000000000000000001')})
        assert request_1['job']['work_dir'] == str(slivka_home / 'jobs' / 'AB' / 'AA' / 'AAAAAAAAAAAA')
