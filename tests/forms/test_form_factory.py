import os.path
import unittest

import jsonschema
import yaml

from pybioas.server.forms import FormFactory
from pybioas.server.forms.fields import *
from pybioas.utils import FORM_SCHEMA


class TestOptionElementParser(unittest.TestCase):

    def setUp(self):
        form_file = os.path.join(
            os.path.dirname(__file__), "SampleForm.yml"
        )
        with open(form_file) as f:
            instance = yaml.load(f)
        jsonschema.validate(instance, FORM_SCHEMA)
        self.fields = instance

    def test_integer_field(self):
        alpha_field = self.fields['alpha']
        field = FormFactory._get_integer_field('alpha', alpha_field)
        self.assertIsInstance(field, IntegerField)
        self.assertEqual(field._min, 0)
        self.assertEqual(field._max, 30)
        self.assertEqual(field.default, 10)

    def test_decimal_field(self):
        beta_field = self.fields['beta']
        beta_field = FormFactory._get_decimal_field('beta', beta_field)
        gamma_field = self.fields['gamma']
        gamma_field = FormFactory._get_decimal_field('gamma', gamma_field)
        self.assertIsInstance(beta_field, DecimalField)
        self.assertIsInstance(gamma_field, DecimalField)

        self.assertTupleEqual(beta_field._min, (0.0, False))
        self.assertTupleEqual(beta_field._max, (10.0, True))
        self.assertTupleEqual(gamma_field._min, (-5.0, True))
        self.assertTupleEqual(gamma_field._max, (20.0, False))

        self.assertEqual(beta_field.default, 2.5)
        self.assertEqual(gamma_field.default, 0.0)

    def test_text_field(self):
        delta_field = self.fields['delta']
        field = FormFactory._get_text_field('delta', delta_field)
        self.assertIsInstance(field, TextField)
        self.assertEqual(field._min_length, 2)
        self.assertEqual(field._max_length, 10)
        self.assertEqual(field.default, "Foo")

    def test_boolean_field(self):
        epsilon_field = self.fields['epsilon']
        field = FormFactory._get_boolean_field('epsilon', epsilon_field)
        self.assertIsInstance(field, BooleanField)
        self.assertTrue(field.default)
        self.assertEqual(field._repr_value, "-e")

    def test_choice_field(self):
        zeta_field = self.fields['zeta']
        field = FormFactory._get_choice_field('zeta', zeta_field)
        self.assertIsInstance(field, ChoiceField)
        self.assertSetEqual(set(field._choices), {"-a", "--b", "-ccc"})

    def test_file_field(self):
        eta_field = self.fields['eta']
        field = FormFactory._get_file_field('eta', eta_field)
        self.assertIsInstance(field, FileField)
        self.assertEqual(field._mimetype, "text/plain")
        self.assertEqual(field._extension, "txt")
        self.assertEqual(field._max_size, 1024 * 20)


class TestForm(unittest.TestCase):

    def setUp(self):
        form_file = os.path.join(
            os.path.dirname(__file__), "LittleForm.yml"
        )
        with open(form_file) as f:
            instance = yaml.load(f)
        jsonschema.validate(instance, FORM_SCHEMA)
        self.LittleForm = FormFactory.get_form_class(
            "LittleForm", "Little", form_file
        )

    def test_separate_option_instances(self):
        form1 = self.LittleForm({"alpha": 5})
        self.LittleForm({"alpha": 8})
        self.assertEqual(form1.cleaned_data['alpha'], 5)

    def test_required_field(self):
        form = self.LittleForm()
        field = next(f for f in form.fields if f.name == 'alpha')
        self.assertTrue(field.required)

    def test_not_required_field(self):
        form = self.LittleForm()
        field = next(f for f in form.fields if f.name == 'beta')
        self.assertFalse(field.required)
