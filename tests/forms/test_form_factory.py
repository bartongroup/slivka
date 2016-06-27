import os.path
import unittest

import jsonschema
import yaml

from server.forms.form_factory import FormFactory
from server.forms.fields import *
from utils import COMMAND_SCHEMA


class TestOptionElementParser(unittest.TestCase):

    def setUp(self):
        form_file = os.path.join(
            os.path.dirname(__file__), "SampleForm.yml"
        )
        with open(form_file) as f:
            instance = yaml.load(f)
        jsonschema.validate(instance, COMMAND_SCHEMA)
        self.fields = instance['options']

    def test_field_details(self):
        element = self.fields[0]
        field = FormFactory._get_integer_field(element)
        self.assertEqual(field.name, "alpha")

    def test_integer_field(self):
        alpha_field = [f for f in self.fields if f['name'] == 'alpha'][0]
        field = FormFactory._get_integer_field(alpha_field)
        self.assertIsInstance(field, IntegerField)
        self.assertEqual(field._min, 0)
        self.assertEqual(field._max, 30)
        self.assertEqual(field.default, 10)

    def test_decimal_field(self):
        beta_field = [f for f in self.fields if f['name'] == 'beta'][0]
        beta_field = FormFactory._get_decimal_field(beta_field)
        gamma_field = [f for f in self.fields if f['name'] == 'gamma'][0]
        gamma_field = FormFactory._get_decimal_field(gamma_field)
        self.assertIsInstance(beta_field, DecimalField)
        self.assertIsInstance(gamma_field, DecimalField)

        self.assertTupleEqual(beta_field._min, (0.0, False))
        self.assertTupleEqual(beta_field._max, (10.0, True))
        self.assertTupleEqual(gamma_field._min, (-5.0, True))
        self.assertTupleEqual(gamma_field._max, (20.0, False))

        self.assertEqual(beta_field.default, 2.5)
        self.assertEqual(gamma_field.default, 0.0)

    def test_text_field(self):
        delta_field = [f for f in self.fields if f['name'] == 'delta'][0]
        field = FormFactory._get_text_field(delta_field)
        self.assertIsInstance(field, TextField)
        self.assertEqual(field._min_length, 2)
        self.assertEqual(field._max_length, 10)
        self.assertEqual(field.default, "Foo")

    def test_boolean_field(self):
        epsilon_field = [f for f in self.fields if f['name'] == 'epsilon'][0]
        field = FormFactory._get_boolean_field(epsilon_field)
        self.assertIsInstance(field, BooleanField)
        self.assertEqual(field.default, True)

    def test_choice_field(self):
        zeta_field = [f for f in self.fields if f['name'] == 'zeta'][0]
        field = FormFactory._get_choice_field(zeta_field)
        self.assertIsInstance(field, ChoiceField)
        self.assertSetEqual(set(field._choices), {"-a", "--b", "-ccc"})


class TestForm(unittest.TestCase):

    def setUp(self):
        form_file = os.path.join(
            os.path.dirname(__file__), "SampleForm.yml"
        )
        with open(form_file) as f:
            instance = yaml.load(f)
        jsonschema.validate(instance, COMMAND_SCHEMA)
        self.SampleForm = FormFactory.get_form_class(
            "SampleForm", "Sample", form_file
        )

    def test_separate_option_instances(self):
        form1 = self.SampleForm({"alpha": 5})
        self.SampleForm({"alpha": 8})
        assert form1.cleaned_data['alpha'] == 5
