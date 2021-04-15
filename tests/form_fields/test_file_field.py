import contextlib
import os.path
from unittest.mock import sentinel

import mongomock
from nose import with_setup
from nose.tools import assert_equal, assert_list_equal, assert_set_equal, \
    raises, assert_raises
from werkzeug.datastructures import MultiDict, FileStorage

import slivka.db
from slivka.db.documents import UploadedFile
from slivka.server.forms.fields import FileField, ValidationError
from slivka.server.forms.file_proxy import FileProxy


def setup_module():
    slivka.db.mongo = mongomock.MongoClient()
    slivka.db.database = slivka.db.mongo.slivkadb

def teardown_module():
    del slivka.db.database
    del slivka.db.mongo


def setup_uploaded_file():
    global uploaded_file
    uploaded_file = UploadedFile(
        title='example-file',
        media_type='text/plain',
        path=os.path.join(os.path.dirname(__file__), 'data', 'lipsum.txt')
    )
    uploaded_file.insert(slivka.db.database)


def test_value_from_multipart():
    field = FileField('test')
    data = MultiDict()
    files = MultiDict({'test': sentinel.file})
    assert_equal(field.fetch_value(data, files), sentinel.file)


def test_value_from_data():
    field = FileField('test')
    data = MultiDict({'test': 'deadbeef'})
    assert_equal(field.fetch_value(data, MultiDict()), 'deadbeef')


def test_multiple_files():
    field = FileField('test', multiple=True)
    data = MultiDict([('test', 'c0ffee'), ('test', 'f00ba4')])
    assert_list_equal(
        field.fetch_value(data, MultiDict()),
        ['c0ffee', 'f00ba4']
    )


def test_multiple_fields_mixed():
    field = FileField('test', multiple=True)
    data = MultiDict([('test', 'c0ffee'), ('test', 'f00ba4')])
    files = MultiDict({'test': sentinel.file})
    assert_set_equal(
        set(field.fetch_value(data, files)),
        {'c0ffee', 'f00ba4', sentinel.file}
    )


@with_setup(setup_uploaded_file)
def test_uploaded_file():
    field = FileField('test')
    file = field.validate(uploaded_file['uuid'])
    with contextlib.closing(file) as stream:
        assert_equal(stream.readline(), b'Lorem ipsum dolor sit amet\n')


@raises(ValidationError)
def test_missing_uploaded_file():
    field = FileField('test')
    field.validate('missing_uuid')


def test_posted_file():
    field = FileField('test')
    path = os.path.join(os.path.dirname(__file__), 'data', 'lipsum.txt')
    fs = FileStorage(
        stream=open(path, 'rb'),
        filename='lipsum.txt',
        name='test'
    )
    file = field.validate(fs)
    with contextlib.closing(file) as stream:
        assert_equal(stream.readline(), b'Lorem ipsum dolor sit amet\n')


@with_setup(setup_uploaded_file)
def test_to_cmd_parameter():
    field = FileField('name')
    wrapper = field.validate(uploaded_file['uuid'])
    assert_equal(field.to_cmd_parameter(wrapper), uploaded_file['path'])


class TestMediaTypeValidation:
    data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def setup(self):
        pass

    def teardown(self):
        pass

    def test_text(self):
        field = FileField("name", media_type='text/plain')
        file = FileProxy(path=os.path.join(self.data_dir, 'lipsum.txt'))
        field.validate(file)

    def test_not_text(self):
        field = FileField("name", media_type='text/plain')
        file = FileProxy(path=os.path.join(self.data_dir, 'example.bin'))
        with assert_raises(ValidationError):
            field.validate(file)

    def test_json(self):
        field = FileField('name', media_type='application/json')
        file = FileProxy(path=os.path.join(self.data_dir, 'example.json'))
        field.validate(file)

    def test_not_json(self):
        field = FileField('name', media_type='application/json')
        file = FileProxy(path=os.path.join(self.data_dir, 'lipsum.txt'))
        with assert_raises(ValidationError):
            field.validate(file)
