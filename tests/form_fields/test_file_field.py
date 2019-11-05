import contextlib
import os.path
import mongomock
import pytest
from unittest.mock import sentinel
from werkzeug.datastructures import MultiDict, FileStorage

from slivka.server.forms.fields import FileField, ValidationError
import slivka.db
from slivka.db.documents import UploadedFile


@pytest.fixture('module')
def mock_mongo():
    slivka.db.mongo = mongomock.MongoClient()
    yield slivka.db.mongo
    del slivka.db.mongo


@pytest.fixture('module')
def mock_uploaded_file(mock_mongo: mongomock.MongoClient):
    file = UploadedFile(
        title='example-file',
        media_type='text/plain',
        path=os.path.join(os.path.dirname(__file__), 'data', 'lipsum.txt')
    )
    file.insert(mock_mongo['slivkadb'])
    return file


def test_value_from_file_data():
    field = FileField('test')
    data = MultiDict()
    files = MultiDict({'test': sentinel.file})
    assert field.value_from_request_data(data, files) == sentinel.file


def test_value_from_data():
    field = FileField('test')
    data = MultiDict({'test': 'deadbeef'})
    assert field.value_from_request_data(data, MultiDict()) == 'deadbeef'


def test_multiple_files():
    field = FileField('test', multiple=True)
    data = MultiDict([('test', 'c0ffee'), ('test', 'f00ba4')])
    assert field.value_from_request_data(data, MultiDict()) == ['c0ffee', 'f00ba4']


def test_multiple_fields_mixed():
    field = FileField('test', multiple=True)
    data = MultiDict([('test', 'c0ffee'), ('test', 'f00ba4')])
    files = MultiDict({'test': sentinel.file})
    assert set(field.value_from_request_data(data, files)) == {'c0ffee', 'f00ba4', sentinel.file}


def test_empty_value():
    field = FileField('test')
    assert field.to_python('') is None


def test_uploaded_file(mock_uploaded_file):
    field = FileField('test')
    file = field.to_python(mock_uploaded_file['uuid'])
    with contextlib.closing(file.stream) as stream:
        assert stream.readline() == b'Lorem ipsum dolor sit amet\n'


@pytest.mark.usefixtures('mock_mongo')
def test_missing_uploaded_file():
    field = FileField('test')
    with pytest.raises(ValidationError):
        field.to_python('missing_uuid')


@pytest.mark.usefixtures('mock_mongo')
def test_posted_file():
    field = FileField('test')
    path = os.path.join(os.path.dirname(__file__), 'data', 'lipsum.txt')
    file = FileStorage(
        stream=open(path, 'rb'),
        filename='lipsum.txt',
        name='test'
    )
    wrapper = field.to_python(file)
    with contextlib.closing(wrapper.stream) as stream:
        assert stream.readline() == b'Lorem ipsum dolor sit amet\n'


def test_to_cmd_parameter(mock_uploaded_file):
    field = FileField('name')
    wrapper = field.to_python(mock_uploaded_file['uuid'])
    assert wrapper.path == mock_uploaded_file['path']
