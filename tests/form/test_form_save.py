import mongomock
import pytest
from werkzeug.datastructures import MultiDict

from server.forms.form import BaseForm
from server.forms.fields import *


class MyForm(BaseForm):
    ints_field = IntegerField('ints', required=False, multiple=True)
    dec_field = DecimalField('dec', required=False)
    choice_field = ChoiceField(
        'choice', choices=[('a', 'A'), ('b', 'B'), ('c', 'C')], required=False
    )
    flag_field = FlagField('flag')


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
        'flag': True
    }
