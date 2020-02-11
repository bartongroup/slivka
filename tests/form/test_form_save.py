from tempfile import TemporaryDirectory
from unittest import mock

import io
import mongomock
import pytest
from werkzeug.datastructures import MultiDict, FileStorage

from slivka.server.forms.fields import *
from slivka.server.forms.form import BaseForm


class MyForm(BaseForm):
    ints_field = IntegerField('ints', required=False, multiple=True)
    dec_field = DecimalField('dec', required=False)
    choice_field = ChoiceField(
        'choice', choices=[('a', 'A'), ('b', 'B'), ('c', 'C')], required=False
    )
    flag_field = FlagField('flag', required=False)
    file_field = FileField('file', required=False)


@pytest.fixture('function')
def database():
    return mongomock.MongoClient().db


def test_save_form(database: mongomock.Database):
    form = MyForm(MultiDict([
        ('ints', '19'), ('ints', '20'), ('ints', '21'),
        ('dec', '12.05'), ('choice', 'a'), ('flag', 'yes')
    ]))
    request = form.save(database)
    job = database[request.__collection__].find_one({'uuid': request.uuid})
    assert job


def test_saved_form_data(database: mongomock.Database):
    form = MyForm(MultiDict([
        ('ints', '19'), ('ints', '20'), ('ints', '21'),
        ('dec', '12.05'), ('choice', 'a'), ('flag', 'yes')
    ]))
    request = form.save(database)
    job = database[request.__collection__].find_one({'uuid': request.uuid})
    assert job['inputs'] == {
        'ints': [19, 20, 21],
        'dec': 12.05,
        'choice': 'A',
        'flag': True,
        'file': None
    }


@pytest.fixture('module')
def temp_dir():
    with TemporaryDirectory() as dirname:
        yield dirname


def test_file_saving(temp_dir, database: mongomock.Database):
    form = MyForm(MultiDict([
        ('file', FileStorage(stream=io.BytesIO(b'hello\n'), content_type='text/plain'))
    ]))
    form.save_location = temp_dir
    with mock.patch('slivka.server.forms.fields.validate_file_content', return_value=True):
        request = form.save(database)
    with open(request['inputs']['file'], 'rb') as f:
        assert f.read() == b'hello\n'
