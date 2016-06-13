import unittest

from server.forms.fields import (
    BaseField, IntegerField, DecimalField, FileField,
    TextField, BooleanField, SelectField
)


class TestBaseField(unittest.TestCase):

    def setUp(self):
        self.field = BaseField(default='foo')

    def test_default(self):
        self.assertEqual(self.field.default, 'foo')
        with self.assertRaises(AttributeError):
            self.field.default = 'bar'

    def test_value(self):
        self.assertEqual(self.field.value, 'foo')
        self.field.value = 'bar'
        self.assertEqual(self.field.value, 'bar')

    def test_invalidation(self):
        self.field._valid = True
        self.assertTrue(self.field.is_valid)
        self.field.value = 'bar'
        self.assertFalse(self.field._valid)


class TestIntegerField(unittest.TestCase):

    def setUp(self):
        self.field = IntegerField(default=4)

    def test_is_valid(self):
        self.field.value = 10
        self.assertTrue(self.field.is_valid)
        self.field.value = "10"
        self.assertTrue(self.field.is_valid)
        self.field.value = "3.5"
        self.assertFalse(self.field.is_valid)
        self.field.value = "-4"
        self.assertTrue(self.field.is_valid)

    def test_cleaned_data(self):
        self.assertEqual(self.field.cleaned_value, 4)
        self.field.value = "True"
        with self.assertRaises(ValueError):
            self.field.cleaned_value
        self.field.value = '10'
        self.assertEqual(self.field.cleaned_value, 10)


class TestDecimalField(unittest.TestCase):

    def setUp(self):
        self.field = DecimalField()

    def test_is_valid(self):
        self.field.value = 3.1415
        self.assertTrue(self.field.is_valid)
        self.field.value = "3.5"
        self.assertTrue(self.field.is_valid)
        self.field.value = "abc"
        self.assertFalse(self.field.is_valid)
        self.field.value = "-2.71"
        self.assertTrue(self.field.is_valid)

    def test_cleaned_data(self):
        self.field.value = 3.1415
        self.assertAlmostEqual(self.field.cleaned_value, 3.1415)
        self.field.value = "foobar"
        with self.assertRaises(ValueError):
            self.field.cleaned_value
        self.field.value = "0.12345678987654321"
        self.assertAlmostEqual(self.field.cleaned_value, 0.12345678)


class TestFileField(unittest.TestCase):

    def setUp(self):
        self.field = FileField()

    def test_is_valid(self):
        self.field.value = ".gitignore"
        self.assertTrue(self.field.is_valid)
        self.field.value = "some_sample_file.fasta"
        self.assertTrue(self.field.is_valid)
        self.field.value = "dot.spaced.file.name"
        self.assertTrue(self.field.is_valid)
        self.field.value = "illegal+character"
        self.assertFalse(self.field.is_valid)
        self.field.value = "legal_character -.-"
        self.assertTrue(self.field.is_valid)
        self.field.value = "  spaces"
        self.assertFalse(self.field.is_valid)


class TestTextField(unittest.TestCase):

    def setUp(self):
        self.field = TextField(default="Qux")

    def test_is_valid(self):
        self.assertTrue(self.field.is_valid)
        self.field.value = "abc"
        self.assertTrue(self.field.is_valid)
        self.field.value = 123
        self.assertTrue(self.field.is_valid)

    def test_cleaned_value(self):
        self.field.value = "abc"
        self.assertEqual(self.field.cleaned_value, "abc")
        self.field.value = 123
        self.assertEqual(self.field.cleaned_value, "123")


class TestBooleanField(unittest.TestCase):

    def setUp(self):
        self.field = BooleanField()

    def test_is_valid(self):
        self.field.value = True
        self.assertTrue(self.field.is_valid)
        self.field.value = "yes"
        self.assertTrue(self.field.is_valid)
        self.field.value = 0
        self.assertTrue(self.field.is_valid)
        self.field.value = None
        self.assertTrue(self.field.is_valid)

    def test_cleaned_data(self):
        self.compare_values(0, False)
        self.compare_values(1, True)
        self.compare_values(False, False)
        self.compare_values(True, True)
        self.compare_values("false", False)
        self.compare_values("true", True)
        self.compare_values("yes", True)
        self.compare_values("no", False)
        self.compare_values("NULL", False)
        self.compare_values("0", False)
        self.compare_values("1", True)
        self.compare_values("None", False)

    def compare_values(self, field_value, expected_value):
        self.field.value = field_value
        self.assertEqual(self.field.cleaned_value, expected_value)


class TestSelectField(unittest.TestCase):

    def setUp(self):
        self.field = SelectField(("alpha", "beta", "gamma"))

    def test_is_valid(self):
        self.field.value = "beta"
        self.assertTrue(self.field.is_valid)
        self.field.value = "delta"
        self.assertFalse(self.field.is_valid)

    def test_cleaned_data(self):
        self.field.value = "gamma"
        self.assertEqual(self.field.cleaned_value, "gamma")
