from copy import deepcopy

import slivka

from slivka.db.models import Request, Option
from slivka.utils import Singleton
from .exceptions import ValidationError
from .fields import (IntegerField, DecimalField, FileField, TextField,
                     BooleanField, ChoiceField)


class BaseForm:
    _fields = {}
    _service = None
    # fields initialized by the FormFactory

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj._fields = deepcopy(cls._fields)
        return obj

    def __init__(self, values=None):
        """
        Creates a form instance with its fields.
        If values are provided binds the form to them and fills the fields.

        :param values: dictionary of values further passed to the fields
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
            return {
                field.name: field.error
                for field in self.fields
                if field.error is not None
            }

    def is_valid(self):
        """
        Checks if the form and all its fields individually are valid.

        :return: boolean that indicates if the orm is valid
        """
        if self._is_valid is None:
            self._is_valid = all(field.is_valid for field in self.fields)
        return self._is_valid

    def save(self, session):
        """
        Adds a new job request to the database session and fills options from
        the form fields.
        Session must be committed after calling this method.

        :param session: a current database session
        :return: request object added to the database session
        :rtype: Request
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


class FormFactory(metaclass=Singleton):

    def __init__(self):
        self._forms = {}
        for conf in slivka.settings.service_configurations.values():
            self.add_form(conf)

    def add_form(self, service_config):
        """
        :type service_config: slivka.settings_provider.ServiceConfigurationProvider
        """
        form_class = self.create_form_class(
            form_name=service_config.service.capitalize() + 'Form',
            service=service_config.service,
            configuration=service_config.form
        )
        self._forms[service_config.service] = form_class

    def get_form_class(self, service):
        return self._forms[service]

    @staticmethod
    def create_form_class(form_name, service, configuration):
        """Constructs a form class from the configuration.

        :param form_name: name given to a new form class
        :param service: service name the form is bound to
        :param configuration: form fields description
        :return: new BaseForm subclass with fields loaded from the param file
        :raise jsonschema.exceptions.ValidationError:
        """
        fields = dict(FormFactory._load_fields(configuration))
        return type(
            form_name, (BaseForm,),
            {
                "_fields": fields,
                "_service": service
            }
        )

    @staticmethod
    def _load_fields(fields):
        """Loads the list of form fields from the json description.

        :param fields: list of field descriptions
        :return: iterable of field objects
        """
        for name, field in fields.items():
            # access the underlying function of the staticmethod object
            # noinspection PyUnresolvedReferences
            factory = FormFactory.field_factory[field['value']['type']].__func__
            yield (name, factory(name, field))

    # todo: move parameters extracting to individual FormField classes
    @staticmethod
    def _get_integer_field(name, field):
        value = field['value']
        assert value['type'] == 'int'
        return IntegerField(
            name,
            label=field["label"],
            description=field.get("description", ""),
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
            label=field["label"],
            description=field.get("description", ""),
            default=value.get("default"),
            required=value.get("required", True),
            minimum=value.get("min"),
            maximum=value.get("max"),
            min_exclusive=value.get("minExclusive", False),
            max_exclusive=value.get("maxExclusive", False)
        )

    @staticmethod
    def _get_text_field(name, field):
        value = field['value']
        assert value['type'] == 'text'
        return TextField(
            name,
            label=field["label"],
            description=field.get("description", ""),
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
            label=field["label"],
            description=field.get("description", ""),
            default=value.get("default"),
            required=value.get("required", True),
        )

    @staticmethod
    def _get_choice_field(name, field):
        value = field['value']
        assert value['type'] == 'choice'
        return ChoiceField(
            name,
            label=field["label"],
            description=field.get("description", ""),
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
            label=field["label"],
            description=field.get("description", ""),
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
