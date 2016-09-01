from copy import deepcopy

import jsonschema
import yaml

from slivka.db.models import Request, Option
from slivka.utils import FORM_SCHEMA
from .exceptions import ValidationError
from .fields import (IntegerField, DecimalField, FileField, TextField,
                     BooleanField, ChoiceField)


class BaseForm:

    # TODO: fields should be a list of fields
    _fields = {}
    _service = None

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj._fields = deepcopy(cls._fields)
        return obj

    def __init__(self, values=None):
        """
        Binds the form to given values and fills its fields.
        :param values: dictionary of values passed to the fields
        """
        self._is_valid = None
        if values is None:
            self._bound = False
            self._is_valid = False
        else:
            self._bound = True
            for field_id, field in self._fields.items():
                field.value = values.get(field_id)

    @property
    def fields(self):
        """
        :return: form fields
        """
        return self._fields.values()

    @property
    def cleaned_data(self):
        if not self.is_valid():
            raise ValidationError('form', "Form invalid.")
        return {
            field.name: field.cleaned_value
            for field in self.fields
        }

    @property
    def errors(self):
        if not self.is_valid():
            return{
                field.name: field.error
                for field in self.fields
                if field.error is not None
            }

    def is_valid(self):
        """
        Checks if the form and its fields are valid.
        :return: boolean that indicates if the orm is valid
        """
        if self._is_valid is None:
            self._is_valid = all(field.is_valid for field in self.fields)
        return self._is_valid

    def save(self, session):
        """
        Adds new request to the session and fills options from the form fields.
        Session must be committed after calling this method.
        :param session: a current database session
        """
        if not self.is_valid():
            raise ValidationError
        request = Request(service=self._service)
        request.options = [
            Option(
                name=field.name,
                value=field.cleaned_value
            )
            for field in self.fields
        ]
        session.add(request)
        return request

    def __repr__(self):
        return "<{}> bound={}".format(self.__class__.__name__, self._bound)


class FormFactory:

    @staticmethod
    def get_form_class(form_name, service, form_file):
        """
        Constructs a form class from a parameters configuration file
        :param form_name: name given to a new form class
        :param service: service name the form is bound to
        :param form_file: a path to json file describing form fields
        :return: new BaseForm subclass with fields loaded from the param file
        :raise jsonschema.exceptions.ValidationError:
        """
        with open(form_file, "r") as f:
            instance = yaml.load(f)
        jsonschema.validate(instance, FORM_SCHEMA)
        fields = list(FormFactory._load_fields(instance))
        return type(
            form_name, (BaseForm, ),
            {
                "_fields": dict(fields),
                "_service": service
            }
        )

    @staticmethod
    def _load_fields(fields):
        """
        Loads the list of form fields from the json description.
        :param fields: list of field descriptions
        :return: iterable of field objects
        """
        for name, field in fields.items():
            factory = FormFactory.field_factory[field['value']['type']].__func__
            yield (name, factory(name, field))

    @staticmethod
    def _get_integer_field(name, field):
        value = field['value']
        assert value['type'] == 'int'
        return IntegerField(
            name,
            minimum=value.get("min"),
            maximum=value.get("max"),
            default=value.get("default"),
            required=value.get("required", True)
        )

    @staticmethod
    def _get_decimal_field(name, field):
        value = field['value']
        assert value['type'] == "float"
        return DecimalField(
            name,
            default=value.get("default"),
            required=value.get("required", True),
            minimum=value.get("min"), maximum=value.get("max"),
            min_exclusive=value.get("minExclusive", False),
            max_exclusive=value.get("maxExclusive", False)
        )

    @staticmethod
    def _get_text_field(name, field):
        value = field['value']
        assert value['type'] == 'text'
        return TextField(
            name,
            default=value.get("default"),
            required=value.get("required", True),
            min_length=value.get("minLength"),
            max_length=value.get("maxLength")
        )

    @staticmethod
    def _get_boolean_field(name, field):
        value = field["value"]
        assert value["type"] == "boolean"
        return BooleanField(
            name,
            default=value.get("default"),
            required=value.get("required", True),
        )

    @staticmethod
    def _get_choice_field(name, field):
        value = field['value']
        assert value['type'] == 'choice'
        return ChoiceField(
            name,
            default=value.get("default"),
            required=value.get("required", True),
            choices=value.get("choices")
        )

    @staticmethod
    def _get_file_field(name, field):
        value = field['value']
        assert value["type"] == "file"
        return FileField(
            name,
            default=value.get("default"),
            required=value.get("required", True),
            extension=value.get("extension"),
            mimetype=value.get("mimetype"),
            max_size=value.get("maxSize")
        )

    field_factory = {
        "int": _get_integer_field,
        "float": _get_decimal_field,
        "text": _get_text_field,
        "boolean": _get_boolean_field,
        "choice": _get_choice_field,
        "file": _get_file_field
    }
