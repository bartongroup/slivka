import os.path

import yaml
from nose.tools import (
    assert_equal, assert_is_instance, assert_true, assert_false,
    assert_is_none, assert_dict_equal, assert_sequence_equal
)

from slivka.server.forms import FormLoader
from slivka.server.forms.fields import *

curdir = os.path.dirname(__file__)


class TestGeneralFieldLoader:
    def setup(self):
        path = os.path.join(
            os.path.dirname(__file__), "data",  "basic_form.yaml")
        data = yaml.safe_load(open(path))
        self.form = FormLoader().read_dict('example', data)

    def test_fields_present(self):
        names = [field.name for field in self.form.fields.values()]
        expected = ['alpha', 'bravo', 'charlie', 'delta']
        assert_sequence_equal(names, expected)

    def test_required_unset(self):
        assert_true(self.form['alpha'].required)

    def test_required_set_false(self):
        assert_false(self.form['bravo'].required)

    def test_required_set_true(self):
        assert_true(self.form['charlie'].required)

    def test_array_type(self):
        assert_is_instance(self.form['delta'], ArrayFieldMixin)


class TestIntFieldLoader:
    def setup(self):
        path = os.path.join(curdir, 'data', 'int_fields.yaml')
        data = yaml.safe_load(open(path))
        self.form = FormLoader().read_dict('int-test', data)
        self.field = self.form['field']
        self.default_field = self.form['default-field']

    def test_type(self):
        assert_is_instance(self.field, IntegerField)

    def test_array_type(self):
        field = self.form['array-field']
        assert_is_instance(field, IntegerArrayField)
        assert_is_instance(field, IntegerField)
        assert_is_instance(field, ArrayFieldMixin)

    def test_label(self):
        assert_equal(self.field.label, 'int field')

    def test_description(self):
        assert_equal(self.field.description, 'An integer value')

    def test_min(self):
        assert_equal(self.field.min, 0)

    def test_max(self):
        assert_equal(self.field.max, 5)

    def test_default(self):
        assert_equal(self.field.default, 0)

    def test_required(self):
        assert_false(self.field.required)

    def test_default_min(self):
        assert_is_none(self.default_field.min)

    def test_default_max(self):
        assert_is_none(self.default_field.max)

    def test_default_default(self):
        assert_is_none(self.default_field.default)

    def test_default_required(self):
        assert_true(self.default_field.required)


class TestFloatFieldLoader:
    def setup(self):
        path = os.path.join(curdir, 'data', 'float_fields.yaml')
        data = yaml.safe_load(open(path))
        self.form = FormLoader().read_dict('float-test', data)
        self.field = self.form['field']
        self.default_field = self.form['default-field']

    def test_type(self):
        assert_is_instance(self.field, DecimalField)

    def test_array_type(self):
        field = self.form['array-field']
        assert_is_instance(field, DecimalArrayField)
        assert_is_instance(field, DecimalField)
        assert_is_instance(field, ArrayFieldMixin)

    def test_min(self):
        assert_equal(self.field.min, 0.5)

    def test_max(self):
        assert_equal(self.field.max, 5.1)

    def test_default(self):
        assert_equal(self.field.default, 1.8)

    def test_min_exclusive(self):
        assert_false(self.field.min_exclusive)

    def test_max_exclusive(self):
        assert_true(self.field.max_exclusive)

    def test_required(self):
        assert_false(self.field.required)

    def test_default_min(self):
        assert_is_none(self.default_field.min)

    def test_default_max(self):
        assert_is_none(self.default_field.max)

    def test_default_min_exclusive(self):
        assert_false(self.default_field.min_exclusive)

    def test_default_max_exclusive(self):
        assert_false(self.default_field.max_exclusive)


class TestTextFieldLoader:
    def setup(self):
        path = os.path.join(curdir, 'data', 'text_fields.yaml')
        data = yaml.safe_load(open(path))
        self.form = FormLoader().read_dict('text-test', data)
        self.field = self.form['field']
        self.default_field = self.form['default-field']

    def test_type(self):
        assert_is_instance(self.field, TextField)

    def test_array_type(self):
        field = self.form['array-field']
        assert_is_instance(field, TextArrayField)
        assert_is_instance(field, TextField)
        assert_is_instance(field, ArrayFieldMixin)

    def test_min_length(self):
        assert_equal(self.field.min_length, 10)

    def test_max_length(self):
        assert_equal(self.field.max_length, 20)

    def test_default(self):
        assert_equal(self.field.default, "default text")

    def test_default_min_length(self):
        assert_is_none(self.default_field.min_length)

    def test_default_max_length(self):
        assert_is_none(self.default_field.max_length)


class TestBooleanFieldLoader:
    def setup(self):
        path = os.path.join(curdir, 'data', 'bool_fields.yaml')
        data = yaml.safe_load(open(path))
        self.form = FormLoader().read_dict('bool-test', data)
        self.field = self.form['field']
        self.default_field = self.form['default-field']

    def test_type(self):
        assert_is_instance(self.field, FlagField)

    def test_array_type(self):
        field = self.form['array-field']
        assert_is_instance(field, BooleanArrayField)
        assert_is_instance(field, BooleanField)
        assert_is_instance(field, ArrayFieldMixin)

    def test_default(self):
        assert_false(self.field.default)

    def test_default_default(self):
        assert_is_none(self.default_field.default)


class TestChoiceFieldLoader:
    def setup(self):
        path = os.path.join(curdir, 'data', 'choice_fields.yaml')
        data = yaml.safe_load(open(path))
        self.form = FormLoader().read_dict('choice-test', data)
        self.field = self.form['field']
        self.default_field = self.form['default-field']

    def test_type(self):
        assert_is_instance(self.field, ChoiceField)

    def test_array_type(self):
        field = self.form['array-field']
        assert_is_instance(field, ChoiceArrayField)
        assert_is_instance(field, ChoiceField)
        assert_is_instance(field, ArrayFieldMixin)

    def test_choices(self):
        expected = {'alpha': 1, 'beta': 2}
        assert_dict_equal(self.field.choices, expected)

    def test_default(self):
        assert_equal(self.field.default, 'alpha')

    def test_default_default(self):
        assert_is_none(self.default_field.default)


class TestFileFieldLoader:
    def setup(self):
        path = os.path.join(curdir, 'data', 'file_fields.yaml')
        data = yaml.safe_load(open(path))
        self.form = FormLoader().read_dict('file-test', data)
        self.field = self.form['field']
        self.default_field = self.form['default-field']

    def test_type(self):
        assert_is_instance(self.field, FileField)

    def test_array_type(self):
        field = self.form['array-field']
        assert_is_instance(field, FileArrayField)
        assert_is_instance(field, FileField)
        assert_is_instance(field, ArrayFieldMixin)

    def test_media_type(self):
        assert_equal(self.field.media_type, "image/*")

    def test_media_type_params(self):
        expected = {'dimensions': '40x40'}
        assert_dict_equal(self.field.media_type_parameters, expected)

    def test_extensions(self):
        expected = ['bmp', 'png', 'jpg']
        assert_sequence_equal(self.field.extensions, expected)

    def test_default_media_type(self):
        assert_is_none(self.default_field.media_type)

    def test_default_media_type_params(self):
        assert_dict_equal(self.default_field.media_type_parameters, {})

    def test_default_extensions(self):
        assert_sequence_equal(self.default_field.extensions, [])
