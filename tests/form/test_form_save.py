import io
from tempfile import TemporaryDirectory
from unittest import mock

import mongomock
import nose
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


def setup_database():
    global database
    database = mongomock.MongoClient().db


def setup_tempdir():
    global tempdir
    tempdir = TemporaryDirectory()


def teardown_tempdir():
    tempdir.cleanup()


@nose.with_setup(setup_database)
def test_save_form():
    form = MyForm(MultiDict([
        ('ints', '19'), ('ints', '20'), ('ints', '21'),
        ('dec', '12.05'), ('choice', 'a'), ('flag', 'yes')
    ]))
    request = form.save(database)
    job = database[request.__collection__].find_one({'uuid': request.uuid})
    assert job


@nose.with_setup(setup_database)
def test_saved_form_data():
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


@nose.with_setup(setup_database)
@nose.with_setup(setup_tempdir, teardown_tempdir)
def test_file_saving():
    form = MyForm(MultiDict([
        ('file', FileStorage(stream=io.BytesIO(b'hello\n'), content_type='text/plain'))
    ]))
    form.fields['file'].save_location = tempdir.name
    with mock.patch('slivka.server.forms.file_validators.validate_file_content', return_value=True):
        request = form.save(database)
    with open(request['inputs']['file'], 'rb') as f:
        assert f.read() == b'hello\n'
