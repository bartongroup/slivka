from datetime import datetime
import os
import shutil
from base64 import urlsafe_b64decode
from importlib import resources

import pytest
import yaml
from bson import ObjectId

from slivka.migrations import migration_1
from slivka.migrations.migration_1 import make_job_path, move_job_directories, resolve_symlinks, ensure_new_style_path


def test_move_job_directories(database, tmp_path):
    collection = database['requests']
    old_dir = tmp_path / 'XXXXXXXXXXXXABCD'
    old_dir.mkdir()
    doc = {
        '_id': ObjectId(urlsafe_b64decode('XXXXXXXXXXXXABCD')),
        'service': 'example',
        'inputs': {},
        'timestamp': datetime(2025, 6, 1, 12, 0),
        'completion_time': datetime(2025, 6, 1, 12, 1),
        'status': 6,
        'runner': 'default',
        'job': {
            'work_dir': str(old_dir),
            'job_id': '0'
        }
    }
    insert_result = collection.insert_one(doc)
    new_dir = tmp_path / 'CD' / 'AB' / 'XXXXXXXXXXXX'
    move_result = list(move_job_directories(collection, str(tmp_path)))
    assert move_result == [(str(old_dir), str(new_dir))]
    assert not old_dir.is_dir()
    assert new_dir.is_dir()
    doc = collection.find_one({"_id" : insert_result.inserted_id})
    assert doc['job']['work_dir'] == str(new_dir)


def test_normalize_symlinks(tmp_path):
    target = tmp_path / 'target.txt'
    target.touch()
    direct_link = tmp_path / 'direct'
    direct_link.symlink_to(target)
    indirect_link = tmp_path / 'indirect'
    indirect_link.symlink_to(direct_link)
    assert indirect_link.readlink() != target
    resolve_symlinks(str(tmp_path))
    assert indirect_link.readlink() == target


@pytest.mark.parametrize(
    ('base_path', 'object_id', 'expected_path'),
    [
        (
            '/home/slivka/',
            ObjectId(urlsafe_b64decode('XXXXXXXXXXXXABCD')),
            '/home/slivka/CD/AB/XXXXXXXXXXXX'
        ),
        (
            '/',
            ObjectId(urlsafe_b64decode('XYZWxyzwXYZWABCD')),
            '/CD/AB/XYZWxyzwXYZW'
        )
    ]
)
def test_make_job_path(base_path, object_id, expected_path):
    assert make_job_path(base_path=base_path, object_id=object_id) == expected_path


@pytest.fixture(scope='class')
def slivka_home(request, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp('slivka_home')
    yield tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture(scope="class")
def project_files(request, slivka_home):
    traversable = request.param
    with resources.as_file(traversable) as path:
        shutil.copytree(path, slivka_home, dirs_exist_ok=True)


@pytest.fixture(scope='class')
def populate_requests_collection(jobs_top_dir, database):
    def insert_documents(items):
        for item in items:
            item['_id'] = ObjectId(item['_id'])
            item['job']['work_dir'] = str(jobs_top_dir / item['job']['work_dir'])
        return list(database['requests'].insert_many(items))
    return insert_documents


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
class TestApplyMigration:
    @pytest.fixture(scope="class", autouse=True)
    def run_migration(self, slivka_home, database, project_files, job_requests):
        migration_1.apply(database, str(slivka_home / "jobs"))

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


@pytest.mark.parametrize(
    'project_files',
    [
        resources.files(__package__) / '0.8.5-flat-directory-project',
    ],
    indirect=['project_files']
)
def test_input_parameters_updated(database, slivka_home, project_files):
    collection = database['requests']
    collection.insert_one({
        '_id': ObjectId(urlsafe_b64decode('AAAAAAAAAAAAAAAA')),
        'service': 'example',
        'inputs': {
            'text': "value"
        },
        'job': {
            'work_dir': str(slivka_home / 'jobs' / 'AAAAAAAAAAAAAAAA'),
            'job_id': '0'
        }
    })
    insert_result_1 = collection.insert_one({
        '_id': ObjectId(urlsafe_b64decode('AAAAAAAAAAAAAAAB')),
        'service': 'example',
        'inputs': {
            'text': 'value',
            'infile': str(slivka_home / 'jobs' / 'AAAAAAAAAAAAAAAA' / 'stdout')
        },
        'job': {
            'work_dir': str(slivka_home / 'jobs' / 'AAAAAAAAAAAAAAAB'),
            'job_id': '1'
        }
    })
    migration_1.apply(database, str(slivka_home / 'jobs'))
    request = collection.find_one({'_id': insert_result_1.inserted_id})
    assert request['inputs']['infile'] == str(slivka_home / 'jobs' / 'AA' / 'AA' / 'AAAAAAAAAAAA' / 'stdout')


@pytest.mark.parametrize(
    'project_files',
    [
        resources.files(__package__) / '0.8.5-flat-directory-project',
    ],
    indirect=['project_files']
)
def test_input_parameters_updated_when_param_is_null(database, slivka_home, project_files):
    collection = database['requests']
    collection.insert_one({
        '_id': ObjectId(urlsafe_b64decode('AAAAAAAAAAAAAAAA')),
        'service': 'example',
        'inputs': {
            'text': 'example'
        },
        'job': {
            'work_dir': str(slivka_home / 'jobs' / 'AAAAAAAAAAAAAAAA'),
            'job_id': '0'
        }
    })
    insert_result_1 = collection.insert_one({
        '_id': ObjectId(urlsafe_b64decode('AAAAAAAAAAAAAAAB')),
        'service': 'example',
        'inputs': {
            'text': None,
            'infile': str(slivka_home / 'jobs' / 'AAAAAAAAAAAAAAAA' / 'stdout')
        },
        'job': {
            'work_dir': str(slivka_home / 'jobs' / 'AAAAAAAAAAAAAAAB'),
            'job_id': '1'
        }
    })
    migration_1.apply(database, str(slivka_home / 'jobs'))
    request = collection.find_one({'_id': insert_result_1.inserted_id})
    assert request['inputs']['infile'] == str(slivka_home / 'jobs' / 'AA' / 'AA' / 'AAAAAAAAAAAA' / 'stdout')


@pytest.mark.parametrize(
    'project_files',
    [
        resources.files(__package__) / '0.8.5-flat-directory-project',
    ],
    indirect=['project_files']
)
def test_input_parameters_updated_when_param_is_list(database, slivka_home, project_files):
    collection = database['requests']
    collection.insert_one({
        '_id': ObjectId(urlsafe_b64decode('AAAAAAAAAAAAAAAA')),
        'service': 'example',
        'inputs': {
            'text': ['example']
        },
        'job': {
            'work_dir': str(slivka_home / 'jobs' / 'AAAAAAAAAAAAAAAA'),
            'job_id': '0'
        }
    })
    insert_result = collection.insert_one({
        '_id': ObjectId(urlsafe_b64decode('AAAAAAAAAAAAAAAB')),
        'service': 'example',
        'inputs': {
            'text': 'example',
            'infile': [str(slivka_home / 'jobs' / 'AAAAAAAAAAAAAAAA' / 'stdout')]
        },
        'job': {
            'work_dir': str(slivka_home / 'jobs' / 'AAAAAAAAAAAAAAAB'),
            'job_id': '1'
        }
    })
    migration_1.apply(database, str(slivka_home / 'jobs'))
    request = collection.find_one({'_id': insert_result.inserted_id})
    assert request['inputs']['infile'] == [str(slivka_home / 'jobs' / 'AA' / 'AA' / 'AAAAAAAAAAAA' / 'stdout')]


@pytest.mark.parametrize(
    ('path', 'top', 'expected_path'),
    [
        pytest.param(
            "/data/jobs/CCCCCCCCCCCCBBAA/stdout",
            "/data/jobs",
            "/data/jobs/AA/BB/CCCCCCCCCCCC/stdout",
            id="old-style path"
        ),
        pytest.param(
            "/data/jobs/AA/BB/CCCCCCCCCCCC/stdout",
            "/data/jobs",
            "/data/jobs/AA/BB/CCCCCCCCCCCC/stdout",
            id="new-style path"
        ),
        pytest.param(
            "/store/data/file.txt",
            "/data/jobs",
            "",
            marks=[pytest.mark.raises(exception=ValueError)],
            id="outside path"
        ),
        pytest.param(
            "input.txt",
            "/data/jobs",
            "",
            marks=[pytest.mark.raises(exception=ValueError)],
            id="not absolute path"
        )
    ]
)
def test_ensure_new_style_path(path, top, expected_path):
    assert ensure_new_style_path(path, top) == expected_path