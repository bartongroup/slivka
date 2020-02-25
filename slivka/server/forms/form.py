import collections
from collections import OrderedDict
from importlib import import_module

from frozendict import frozendict
from typing import Type
from werkzeug.datastructures import MultiDict

import slivka
from slivka.db.documents import JobRequest
from slivka.utils import Singleton, cached_property
from .fields import *


class DeclarativeFormMetaclass(type):
    """
    A metaclass allowing the form fields to be defined as class attributes.
    All attributes which are instances of ``BaseField`` are moved to the
    ``fields`` property - a mapping from field names to field objects.
    """
    @classmethod
    def __prepare__(mcs, name, bases):
        return OrderedDict()

    def __new__(mcs, name, bases, attrs):
        fields = OrderedDict()
        for key, field in list(attrs.items()):
            if isinstance(field, BaseField):
                fields[field.name] = field
                attrs.pop(key)
        attrs['fields'] = fields
        return super().__new__(mcs, name, bases, attrs)


class BaseForm(metaclass=DeclarativeFormMetaclass):
    """
    The base class for all forms. It uses ``DeclarativeFormMetaclass``
    as its metaclass so all deriving forms will have fields automatically
    populated from class' attributes.
    The class also adds essential form functionality such as data storage,
    validation and saving.
    All forms deriving from this class are the containers of fields
    and user input data.
    """
    service = ''
    save_location = cached_property(lambda self: slivka.settings.uploads_dir)

    def __init__(self, data=None, files=None):
        """
        Constructs the form with the data coming from the web request.
        If the data or files are provided, the "bound" form will be created
        which can be used to validate and save the request.
        Otherwise, the unbound form can be used to retrieve field information.

        :param data: request parameters
        :type data: MultiDict
        :param files: multipart request files
        :type data: MultiDict
        """
        self.is_bound = not (data is None and files is None)
        self.data = MultiDict() if data is None else data
        self.files = MultiDict() if files is None else files
        self._errors = None
        self._cleaned_data = frozendict()

    @property
    def errors(self) -> collections.Mapping:
        """ Performs the validation if not done yet and returns errors. """
        if self._errors is None:
            self.full_clean()
        return self._errors

    @property
    def cleaned_data(self) -> collections.Mapping:
        """ Returns the cleaned form data after validation. """
        return self._cleaned_data

    def is_valid(self):
        """ Check whether the data is valid. """
        return self.is_bound and not self.errors

    def full_clean(self):
        """ Performs full validation of the input data. """
        errors = {}
        if not self.is_bound:
            return
        cleaned_data = {}
        for name, field in self.fields.items():
            value = field.value_from_request_data(self.data, self.files)
            try:
                value = field.validate(value)
                cleaned_data[name] = value
            except ValidationError as err:
                errors[field.name] = err
        self._errors = frozendict(errors)
        self._cleaned_data = frozendict(cleaned_data)

    def __iter__(self):
        return iter(self.fields.values())

    def __getitem__(self, item):
        return self.fields[item]

    def save(self, database) -> JobRequest:
        """
        If the form is valid, saves a new request to the database containing
        the cleaned input data.

        :param database: mongo database instance
        :return: created request
        """
        if not self.is_valid():
            raise RuntimeError(self.errors, 'invalid_form')
        inputs = {}
        for name, field in self.fields.items():
            value = self.cleaned_data[name]
            inputs[name] = field.serialize_value(value)
        request = JobRequest(service=self.service, inputs=inputs)
        request.insert(database)
        return request


class FormLoader(metaclass=Singleton):
    """
    A helper factory dynamically creating the forms from the configuration.
    Only a single instance of the class is created (subsequent constructor
    calls return the same object) providing a single point where all
    forms can be accessed from.
    """
    def __init__(self):
        self._forms = {}

    def read_settings(self):
        """Load forms from global settings."""
        for service in slivka.settings.services.values():
            self.read_dict(service.name, service.form)

    def read_dict(self, name: str,  dictionary: dict) -> Type:
        """Load form definition from dictionary.

        :param name: service name
        :param dictionary: form configuration dictionary
        :return: loaded form class
        """
        attrs = OrderedDict(
            (key, self._build_field(key, val))
            for key, val in dictionary.items()
        )
        attrs['service'] = name
        self._forms[name] = cls = DeclarativeFormMetaclass(
            name.capitalize() + 'Form', (BaseForm,), attrs
        )
        return cls

    def __getitem__(self, item):
        """ Retrieve form class by service name. """
        return self._forms[item]

    @staticmethod
    def _build_field(name, field_dict) -> BaseField:
        """ Constructs a field from the configuration """
        value_dict = field_dict['value']
        field_type = value_dict['type']
        common_kwargs = {
            'name': name,
            'label': field_dict['label'],
            'description': field_dict.get('description'),
            'default': value_dict.get('default'),
            'required': value_dict.get('required', True),
            'multiple': value_dict.get('multiple', False)
        }
        if field_type == 'int':
            return IntegerField(
                **common_kwargs,
                min=value_dict.get('min'),
                max=value_dict.get('max')
            )
        elif field_type == 'float' or field_type == 'decimal':
            return DecimalField(
                **common_kwargs,
                min=value_dict.get('min'),
                max=value_dict.get('max'),
                min_exclusive=value_dict.get('min-exclusive', False),
                max_exclusive=value_dict.get('max-exclusive', False)
            )
        elif field_type == 'text':
            return TextField(
                **common_kwargs,
                min_length=value_dict.get('min-length'),
                max_length=value_dict.get('max-length')
            )
        elif field_type == 'boolean' or field_type == 'flag':
            return FlagField(
                **common_kwargs
            )
        elif field_type == 'choice':
            return ChoiceField(
                **common_kwargs,
                choices=value_dict.get('choices')
            )
        elif field_type == 'file':
            return FileField(
                **common_kwargs,
                extensions=value_dict.get('extensions', ()),
                media_type=value_dict.get('media-type'),
                media_type_parameters=value_dict.get('media-type-parameters')
            )
        else:
            # if ``field_type`` is not a recognised type, try importing the
            # custom field using the type as a classpath.
            kwargs = common_kwargs
            kwargs.update(value_dict)
            kwargs.pop("type")
            try:
                mod, attr = field_type.rsplit('.', 1)
                cls = getattr(import_module(mod), attr)
                return cls(**kwargs)
            except (ValueError, AttributeError):
                raise ValueError('Invalid field type "%r"' % field_type)
