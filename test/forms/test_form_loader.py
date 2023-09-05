import os.path

import pytest
import yaml

from test.tools import in_any_order
from slivka.server import FormLoader
from slivka.server.forms.fields import *


@pytest.fixture(scope="class")
def form(request):
    mark = request.node.get_closest_marker("form_file")
    if not mark or not mark.args:
        return
    path = os.path.join(os.path.dirname(__file__), "data", mark.args[0])
    return FormLoader().read_dict("example", yaml.safe_load(open(path)))


@pytest.mark.form_file("basic_form.yaml")
class TestBasicFormLoader:
    def test_field_ids(self, form):
        assert [field.id for field in form.fields.values()] == [
            "alpha",
            "bravo",
            "charlie",
            "delta",
        ]

    @pytest.mark.parametrize("param_id", ["alpha", "bravo", "charlie", "delta"])
    def test_field_name(self, form, param_id):
        assert form[param_id].name == "example label"

    def test_field_required_unset_then_is_required(self, form):
        assert form["alpha"].required is True

    def test_field_required_is_false_then_is_not_required(self, form):
        assert form["bravo"].required is False

    def test_field_required_is_true_then_is_required(self, form):
        assert form["charlie"].required is True

    def test_field_is_instance_of_base_field(self, form):
        assert isinstance(form["alpha"], BaseField)

    def test_array_type_is_instance_of_array_field_mixin(self, form):
        assert isinstance(form["delta"], ArrayFieldMixin)


@pytest.mark.form_file("int_fields.yaml")
class TestIntFieldLoader:
    def test_instance_of_field(self, form):
        assert isinstance(form["field"], IntegerField)

    def test_instance_of_array_field(self, form):
        assert isinstance(form["array-field"], IntegerArrayField)
        assert isinstance(form["array-field"], IntegerField)
        assert isinstance(form["array-field"], ArrayFieldMixin)

    def test_min_set(self, form):
        assert form["field"].min == 0

    def test_max_set(self, form):
        assert form["field"].max == 5

    def test_min_unset(self, form):
        assert form["default-field"].min is None

    def test_max_unset(self, form):
        assert form["default-field"].max is None

    def test_default_set(self, form):
        assert form["field"].default == 0

    def test_default_unset(self, form):
        assert form["default-field"].default is None


@pytest.mark.form_file("float_fields.yaml")
class TestFloatFieldLoader:
    def test_instance_of_field(self, form):
        assert isinstance(form["field"], DecimalField)

    def test_instance_of_array_field(self, form):
        assert isinstance(form["array-field"], DecimalArrayField)
        assert isinstance(form["array-field"], DecimalField)
        assert isinstance(form["array-field"], ArrayFieldMixin)

    def test_min_set(self, form):
        assert form["field"].min == 0.5

    def test_max_set(self, form):
        assert form["field"].max == 5.1

    def test_default_set(self, form):
        assert form["field"].default == 1.8

    def test_min_exclusive_set(self, form):
        assert form["field"].min_exclusive is False

    def test_max_exclusive_set(self, form):
        assert form["field"].max_exclusive is True

    def test_min_unset(self, form):
        assert form["default-field"].min is None

    def test_max_unset(self, form):
        assert form["default-field"].max is None

    def test_min_exclusive_unset(self, form):
        assert form["default-field"].min_exclusive is False

    def test_max_exclusive_unset(self, form):
        assert form["default-field"].max_exclusive is False


@pytest.mark.form_file("text_fields.yaml")
class TestTextFieldLoader:
    def test_instance_of_field(self, form):
        assert isinstance(form["field"], TextField)

    def test_instance_of_array_field(self, form):
        assert isinstance(form["array-field"], TextArrayField)
        assert isinstance(form["array-field"], TextField)
        assert isinstance(form["array-field"], ArrayFieldMixin)

    def test_min_length_set(self, form):
        assert form["field"].min_length == 10

    def test_max_length_set(self, form):
        assert form["field"].max_length == 20

    def test_min_length_unset(self, form):
        assert form["default-field"].min_length is None

    def test_max_length_unset(self, form):
        assert form["default-field"].max_length is None


@pytest.mark.form_file("bool_fields.yaml")
class TestBooleanFieldLoader:
    def test_instance_of_field(self, form):
        assert isinstance(form["field"], BooleanField)

    def test_instance_of_array_field(self, form):
        assert isinstance(form["array-field"], BooleanArrayField)
        assert isinstance(form["array-field"], BooleanField)
        assert isinstance(form["array-field"], ArrayFieldMixin)

    def test_default_set(self, form):
        assert form["field"].default is False

    def test_default_unset(self, form):
        assert form["default-field"].default is None


@pytest.mark.form_file("choice_fields.yaml")
class TestChoiceFieldLoader:
    def test_instance_of_field(self, form):
        assert isinstance(form["field"], ChoiceField)

    def test_instance_of_array_field(self, form):
        assert isinstance(form["array-field"], ChoiceArrayField)
        assert isinstance(form["array-field"], ChoiceField)
        assert isinstance(form["array-field"], ArrayFieldMixin)

    def test_choices(self, form):
        assert form["field"].choices == {"alpha": 1, "beta": 2}

    def test_default_set(self, form):
        assert form["field"].default == "alpha"


@pytest.mark.form_file("file_fields.yaml")
class TestFileFieldLoader:
    def test_instance_of_field(self, form):
        assert isinstance(form["field"], FileField)

    def test_instance_of_array_field(self, form):
        assert isinstance(form["array-field"], FileArrayField)
        assert isinstance(form["array-field"], FileField)
        assert isinstance(form["array-field"], ArrayFieldMixin)

    def test_media_type_set(self, form):
        assert form["field"].media_type == "image/*"

    def test_extensions_set(self, form):
        assert form["field"].extensions == in_any_order("bmp", "png", "jpg")

    def test_media_type_parameters(self, form):
        assert form["field"].media_type_parameters == {"dimensions": "40x40"}

    def test_media_type_unset(self, form):
        assert form["default-field"].media_type is None

    @pytest.mark.xfail(reason="should be none if unset")
    def test_extensions_unset(self, form):
        # empty array suggests no media type allowed
        assert form["default-field"].extensions is None

    def test_media_type_parameters_unset(self, form):
        assert form["default-field"].media_type_parameters == {}


class CustomField(BaseField):
    def __init__(self, *args, alpha=None, bravo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.alpha = alpha
        self.bravo = bravo


@pytest.mark.form_file("custom_fields.yaml")
class TestCustomFieldLoader:
    def test_instance_of_field(self, form):
        assert isinstance(form["field"], CustomField)

    def test_instance_of_array_field(self, form):
        assert isinstance(form["array-field"], CustomField)
        assert isinstance(form["array-field"], ArrayFieldMixin)

    def test_parameters_set(self, form):
        assert form["field"].alpha == 13
        assert form["field"].bravo == 97
