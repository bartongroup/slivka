import unittest

from server.forms.fields import (
    BaseField, IntegerField, DecimalField, FileField,
    TextField, BooleanField, SelectField
)
from server.forms.exceptions import ValidationError


class TestBaseFieldValid(unittest.TestCase):

    def setUp(self):
        self.BaseFieldWrapper = type(
            'BaseField', (BaseField,),
            {"validate": lambda self, value: value}
        )

    def test_type(self):
        field = self.BaseFieldWrapper('')
        self.assertEqual(field.type, "base")

    def test_default(self):
        field = self.BaseFieldWrapper('', default='foo')
        self.assertEqual(field.default, 'foo')
        with self.assertRaises(AttributeError):
            field.default = 'bar'
        self.assertEqual(field.value, 'foo')

    def test_value(self):
        field = self.BaseFieldWrapper('', default="foo")
        self.assertEqual(field.value, "foo")
        field.value = 'bar'
        self.assertEqual(field.value, 'bar')

    def test_invalidation(self):
        field = self.BaseFieldWrapper('', default='foo')
        field._valid = True
        self.assertTrue(field.is_valid)
        field.value = 'bar'
        self.assertFalse(field._valid)

    def test_is_valid(self):
        field = self.BaseFieldWrapper('')
        self.assertTrue(field.is_valid)

    def test_error(self):
        field = self.BaseFieldWrapper('')
        self.assertIsNone(field.error)


class TestIntegerField(unittest.TestCase):

    def test_is_valid_int(self):
        field = IntegerField('')
        field.value = 10
        self.assertTrue(field.is_valid)
        field.value = "10"
        self.assertTrue(field.is_valid)
        field.value = "3.5"
        self.assertFalse(field.is_valid)
        field.value = "-4"
        self.assertTrue(field.is_valid)
        
    def test_is_valid_min(self):
        field = IntegerField('', minimum=-10)
        field.value = -10
        self.assertTrue(field.is_valid)
        field.value = -11
        self.assertFalse(field.is_valid)
        
    def test_is_valid_max(self):
        field = IntegerField('',maximum=20)
        field.value = 20
        self.assertTrue(field.is_valid)
        field.value = 21
        self.assertFalse(field.is_valid)

    def test_cleaned_data(self):
        field = IntegerField('', default=4)
        self.assertEqual(field.cleaned_value, 4)
        field.value = "True"
        with self.assertRaises(ValidationError):
            field.cleaned_value
        field.value = '10'
        self.assertEqual(field.cleaned_value, 10)


class TestDecimalField(unittest.TestCase):

    def test_is_valid_decimal(self):
        field = DecimalField('')
        field.value = 3.1415
        self.assertTrue(field.is_valid)
        field.value = "3.5"
        self.assertTrue(field.is_valid)
        field.value = "abc"
        self.assertFalse(field.is_valid)
        field.value = "-2.71"
        self.assertTrue(field.is_valid)

    def test_cleaned_data(self):
        field = DecimalField('')
        field.value = 3.1415
        self.assertAlmostEqual(field.cleaned_value, 3.1415)
        field.value = "foobar"
        with self.assertRaises(ValueError):
            field.cleaned_value
        field.value = "0.12345678987654321"
        self.assertAlmostEqual(field.cleaned_value, 0.12345678)
        
    def test_is_valid_min_inclusive(self):
        field = DecimalField('', minimum=5, min_exclusive=False)
        field.value = 5
        self.assertTrue(field.is_valid)
        field.value = 4.99
        self.assertFalse(field.is_valid)
        
    def test_is_valid_min_exclusive(self):
        field = DecimalField('', minimum=5, min_exclusive=True)
        field.value = 5
        self.assertFalse(field.is_valid)
        field.value = 4.99
        self.assertFalse(field.is_valid)
        field.value = 5.01
        self.assertTrue(field.is_valid)

    def test_is_valid_max_inclusive(self):
        field = DecimalField('', maximum=5, max_exclusive=False)
        field.value = 5
        self.assertTrue(field.is_valid)
        field.value = 5.01
        self.assertFalse(field.is_valid)

    def test_is_valid_exclusive(self):
        field = DecimalField('', maximum=5, max_exclusive=True)
        field.value = 5
        self.assertFalse(field.is_valid)
        field.value = 5.01
        self.assertFalse(field.is_valid)
        field.value = 4.99
        self.assertTrue(field.is_valid)


class TestFileField(unittest.TestCase):

    def test_is_valid_filename(self):
        field = FileField('')
        for value in [".gitignore", "some_sample_file.fasta",
                      "legal_character -.-", "dot.spaced.file.name"]:
            field.value = value
            self.assertTrue(field.is_valid, "Invalid for %r" % value)

        for value in ["illegal+character", "  spaces"]:
            field.value = value
            self.assertFalse(field.is_valid, "Valid for %r" % value)

    def test_is_valid_extension(self):
        field = FileField('', extension='exe')
        field.value = "runme.bat"
        self.assertFalse(field.is_valid)
        field.value = "executable.exe"
        self.assertTrue(field.is_valid)
        field.value = "myexec.mexe"
        self.assertFalse(field.is_valid)


class TestTextField(unittest.TestCase):

    def test_is_valid(self):
        field = TextField('')
        field.value = "abc"
        self.assertTrue(field.is_valid)
        field.value = 123
        self.assertTrue(field.is_valid)

    def test_cleaned_value(self):
        field = TextField('')
        field.value = "abc"
        self.assertEqual(field.cleaned_value, "abc")
        field.value = 123
        self.assertEqual(field.cleaned_value, "123")

    def test_is_valid_max_length(self):
        field = TextField('', max_length=10)
        field.value = "some very long message goes here"
        self.assertFalse(field.is_valid)
        field.value = "short text"
        self.assertTrue(field.is_valid)

    def test_is_valid_min_length(self):
        field = TextField('', min_length=10)
        field.value = "tiny"
        self.assertFalse(field.is_valid)
        field.value = "short text"
        self.assertTrue(field.is_valid)


class TestBooleanField(unittest.TestCase):

    def setUp(self):
        self.field = BooleanField('')

    def test_is_valid(self):
        self.field.value = True
        self.assertTrue(self.field.is_valid)
        self.field.value = "yes"
        self.assertTrue(self.field.is_valid)
        self.field.value = 0
        self.assertTrue(self.field.is_valid)
        self.field.value = None
        self.assertTrue(self.field.is_valid)

    def test_cleaned_data_true(self):
        for value in [1, True, 'yes', 'true', 'TRUE', 'True', 'LOL', '1',
                      object(), type('', (), {})]:
            self.field.value = value
            self.assertEqual(
                self.field.cleaned_value, True,
                "invalid value for %s" % value
            )

    def test_cleaned_data_false(self):
        for value in [0, False, 'no', 'false', 'FALSE', 'False', 'NULL',
                      'none', '0', (), None]:
            self.assertEqual(
                self.field.cleaned_value, False,
                "invalid value for %r" % (value, )
            )


class TestSelectField(unittest.TestCase):

    def setUp(self):
        self.field = SelectField('', choices=("alpha", "beta", "gamma"))

    def test_is_valid(self):
        self.field.value = "alpha"
        self.assertTrue(self.field.is_valid)
        self.field.value = "beta"
        self.assertTrue(self.field.is_valid)
        self.field.value = "gamma"
        self.assertTrue(self.field.is_valid)
        self.field.value = "delta"
        self.assertFalse(self.field.is_valid)

    def test_cleaned_data(self):
        self.field.value = "gamma"
        self.assertEqual(self.field.cleaned_value, "gamma")
