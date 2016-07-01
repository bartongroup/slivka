from copy import deepcopy

import jsonschema
import yaml

from pybioas.db.models import Request, Option
from pybioas.utils import COMMAND_SCHEMA
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

    def to_dict(self):
        return {
            "fields": [
                {
                    "name": field.name,
                    "type": field.type,
                    "required": field.required,
                    "default": field.default
                }
                for field in self.fields
            ]
        }

    def __repr__(self):
        return "<{}> bound={}".format(self.__class__.__name__, self._bound)


class FormFactory:

    @staticmethod
    def get_form_class(form_name, service, command_file):
        """
        Constructs a form class from a parameters configuration file
        :param form_name: name given to a new form class
        :param service: service name the form is bound to
        :param command_file: a path to json file describing form fields
        :return: new BaseForm subclass with fields loaded from the param file
        :raise jsonschema.exceptions.ValidationError:
        """
        with open(command_file, "r") as f:
            instance = yaml.load(f)
        jsonschema.validate(instance, COMMAND_SCHEMA)
        fields = list(FormFactory._load_fields(instance['options']))
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
        for field in fields:
            factory = FormFactory.field_factory[field['value']['type']].__func__
            yield (field['name'], factory(field))

    @staticmethod
    def _get_integer_field(field):
        value = field['value']
        assert value['type'] == 'integer'
        return IntegerField(
            field['name'],
            minimum=value.get("min"),
            maximum=value.get("max"),
            default=value.get("default")
        )

    @staticmethod
    def _get_decimal_field(field):
        value = field['value']
        assert value['type'] == "decimal"
        return DecimalField(
            field['name'],
            default=value.get("default"),
            minimum=value.get("min"), maximum=value.get("max"),
            min_exclusive=value.get("minExclusive", False),
            max_exclusive=value.get("maxExclusive", False)
        )

    @staticmethod
    def _get_text_field(field):
        value = field['value']
        assert value['type'] == 'text'
        return TextField(
            field["name"],
            default=value.get("default"),
            min_length=value.get("minLength"),
            max_length=value.get("maxLength")
        )

    @staticmethod
    def _get_boolean_field(field):
        value = field["value"]
        assert value["type"] == "boolean"
        return BooleanField(
            field["name"],
            default=value.get("default")
        )

    @staticmethod
    def _get_choice_field(field):
        value = field['value']
        assert value['type'] == 'choice'
        return ChoiceField(
            field["name"],
            default=value.get("default"),
            choices=value.get("choices", {}).values()
        )

    @staticmethod
    def _get_file_field(field):
        value = field['value']
        assert value["type"] == "file"
        return FileField(
            field["name"],
            default=value.get("default"),
            extension=value.get("extension")
        )

    field_factory = {
        "integer": _get_integer_field,
        "decimal": _get_decimal_field,
        "text": _get_text_field,
        "boolean": _get_boolean_field,
        "choice": _get_choice_field,
        "file": _get_file_field
    }
