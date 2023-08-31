import pytest
from slivka.server.forms.form import *


class MyForm1(BaseForm):
    field1 = IntegerField('int', min=0, max=10, default=1)
    field1a = IntegerField('int2', required=False, default=2)
    field1b = IntegerField('int3', required=False)
    field2 = IntegerArrayField('m_int', required=False)
    field3 = IntegerArrayField('m_int2', required=False)
    field4 = IntegerArrayField('m_int3', required=False)
    field5 = DecimalField('float', min=0.0, max=10.0, required=False)
    field6 = TextField('text', required=False)
    field7 = BooleanField('bool')
    field8 = BooleanField('bool2', required=False)
    CHOICES = [('a', 'A'), ('b', 'B'), ('c', 'C')]
    field9 = ChoiceField('choice', choices=CHOICES)
    field10 = ChoiceArrayField('m_choice', choices=CHOICES)


@pytest.fixture(scope='class')
def valid_form1():
    form = MyForm1(MultiDict([
        ('int', '5'),
        ('m_int', '10'), ('m_int', '15'), ('m_int', '0'),
        ('m_int2', '2'),
        ('float', '5.0'),
        ('text', 'foo bar baz'),
        ('bool', 'yes'),
        ('bool2', 'no'),
        ('choice', 'a'),
        ('m_choice', 'a'),
        ('m_choice', 'c')
    ]))
    assert form.is_valid()
    return form


def test_valid_form_cleaned_data(valid_form1):
    assert valid_form1.cleaned_data == {
        'int': 5,
        'int2': 2,
        'int3': None,
        'm_int': [10, 15, 0],
        'm_int2': [2],
        'm_int3': None,
        'float': 5.0,
        'text': 'foo bar baz',
        'bool': True,
        'bool2': None,
        'choice': 'a',
        'm_choice': ['a', 'c']
    }


class MyForm2(BaseForm):
    field1 = IntegerField('int1')
    field2 = IntegerField('int2', default=0, condition="self > int1")
    field3 = IntegerField('int3', required=False, condition="self > int1")


@pytest.fixture(scope='function')
def form2(form_inputs):
    form = MyForm2(MultiDict(form_inputs.items()))
    form.full_clean()
    return form


@pytest.mark.parametrize(
    'form_inputs, expected_cleaned',
    [
        ({'int1': 1}, {'int1': 1, 'int2': None, 'int3': None}),
        ({'int1': 1, 'int3': None}, {'int1': 1, 'int2': None, 'int3': None}),
        ({'int1': -1}, {'int1': -1, 'int2': 0, 'int3': None}),
        ({'int1': 1, 'int3': 2}, {'int1': 1, 'int2': None, 'int3': 2}),
        ({'int1': -1, 'int3': 1}, {'int1': -1, 'int2': 0, 'int3': 1}),
    ]
)
def test_cleaned_data_for_conditions_if_valid_values(form2, expected_cleaned):
    assert form2.cleaned_data == expected_cleaned


@pytest.mark.parametrize(
    'form_inputs',
    [
        {'int1': 1, 'int2': 0},
        {'int1': 2, 'int2': 1},
        {'int1': None},
        {'int1': 3, 'int3': 2}
    ]
)
def test_invalid_form_for_conditions(form2):
    assert not form2.is_valid()
