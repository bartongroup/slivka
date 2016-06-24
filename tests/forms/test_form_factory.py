import os.path
import unittest

from server.forms.form_factory import FormFactory
from utils import validate_form_file


class TestOptionElementParser(unittest.TestCase):

    param_file = os.path.join(
        os.path.dirname(__file__), "SampleForm.xml"
    )
    xml_tree = validate_form_file(param_file)
    root = xml_tree.getroot()

    def test_field_details(self):
        element = self.root[0]
        name, field = FormFactory._parse_field_element(element)
        self.assertEqual(field.name, "alpha")

    def test_integer_field(self):
        alpha_element = self.root.xpath("field[@name='alpha']")[0]
        name, field = FormFactory._parse_field_element(alpha_element)
        self.assertIsInstance(field, FormFactory.field_classes['integer'])
        self.assertEqual(field._min, 0)
        self.assertEqual(field._max, 30)
        self.assertEqual(field.default, 10)

    def test_decimal_field(self):
        beta_element = self.root.xpath("field[@name='beta']")[0]
        name, beta_field = FormFactory._parse_field_element(beta_element)
        gamma_element = self.root.xpath("field[@name='gamma']")[0]
        name, gamma_field = FormFactory._parse_field_element(gamma_element)
        self.assertIsInstance(beta_field, FormFactory.field_classes['decimal'])
        self.assertIsInstance(gamma_field, FormFactory.field_classes['decimal'])

        self.assertTupleEqual(beta_field._min, (0.0, True))
        self.assertTupleEqual(beta_field._max, (10.0, False))
        self.assertTupleEqual(gamma_field._min, (-5.0, False))
        self.assertTupleEqual(gamma_field._max, (20.0, True))

        self.assertEqual(beta_field.default, 2.5)
        self.assertEqual(gamma_field.default, 0.0)

    def test_text_field(self):
        delta_element = self.root.xpath("field[@name='delta']")[0]
        name, field = FormFactory._parse_field_element(delta_element)
        self.assertIsInstance(field, FormFactory.field_classes['text'])
        self.assertEqual(field._min_length, 2)
        self.assertEqual(field._max_length, 10)
        self.assertEqual(field.default, "Foo")

    def test_boolean_field(self):
        epsilon_element = self.root.xpath("field[@name='epsilon']")[0]
        name, field = FormFactory._parse_field_element(epsilon_element)
        self.assertIsInstance(field, FormFactory.field_classes['boolean'])
        self.assertEqual(field.default, True)

    def test_select_field(self):
        zeta_element = self.root.xpath("field[@name='zeta']")[0]
        name, field = FormFactory._parse_field_element(zeta_element)
        self.assertIsInstance(field, FormFactory.field_classes['select'])
        self.assertListEqual(field._choices, ["-a", "--b", "--ccc"])
