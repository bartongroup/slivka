import collections.abc
from collections import OrderedDict, ChainMap
from importlib import import_module
from typing import Optional, Iterator, Mapping, Type

from frozendict import frozendict
from werkzeug.datastructures import MultiDict

from slivka.conf import ServiceConfig
from slivka.db.documents import JobRequest
from .fields import *


class DeclarativeFormMetaclass(type):
    """
    A metaclass allowing the form fields to be defined as class attributes.
    All attributes which are instances of :py:class:`BaseField` are moved to the
    :py:attr:`fields` property - a mapping of field names to field objects.
    """

    @classmethod
    def __prepare__(mcs, name, bases):
        return OrderedDict()

    def __new__(mcs, name, bases, attrs):
        fields = OrderedDict()
        for key, field in list(attrs.items()):
            if isinstance(field, BaseField):
                fields[field.id] = field
                attrs.pop(key)
        attrs['fields'] = fields
        return super().__new__(mcs, name, bases, attrs)

    def __iter__(cls):
        return iter(cls.fields.values())

    def __getitem__(cls, item):
        return cls.fields[item]


class BaseForm(metaclass=DeclarativeFormMetaclass):
    """
    The base class for all forms. It uses :py:class:`DeclarativeFormMetaclass`
    as its metaclass so all deriving forms will have fields automatically
    populated from class attributes. The class also provides form
    functionality such as data storage, validation and saving.
    If the data or files are provided, the "bound" form will be created
    which can be used to validate and save the request.
    Otherwise, the unbound form can be used to retrieve field information.
    Typically, form objects are created by the server components
    and are populated with request data.

    This class' functionality was heavily inspired by django forms.

    :param data: POST request form data, defaults to None
    :param files: files sent with multipart form, defaults to None
    """
    _service = ''

    @property
    def service(self):
        return self._service

    def __init__(self,
                 data: Optional[MultiDict] = None,
                 files: Optional[MultiDict] = None):
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
    def errors(self) -> Mapping[str, ValidationError]:
        """ Performs the full clean if not done yet and returns errors. """
        if self._errors is None:
            self.full_clean()
        return self._errors

    @property
    def cleaned_data(self) -> Mapping:
        """ Returns the validated form data. """
        # TODO: perform full clean if empty
        return self._cleaned_data

    def is_valid(self):
        """ Check whether the form data is valid. """
        return self.is_bound and not self.errors

    def full_clean(self):
        """ Performs full validation of the input data.
        If the form is bound, retrieves the value from the request
        data for each registered field. Then, validates the values
        against corresponding fields and populates
        :py:attr:`cleaned_data` and :py:attr:`errors`.

        .. seealso:: methods of :py:class:`fields.BaseField`
        """
        if not self.is_bound:
            return
        errors = {}
        default_values = {
            field.id: field.default for field in self.fields.values()
        }
        provided_values = {}
        for field in self.fields.values():
            value = field.fetch_value(self.data, self.files)
            try:
                value = field.validate(value)
                if value is not None:
                    provided_values[field.id] = value
            except ValidationError as err:
                errors[field.id] = err
        if errors:
            self._errors = frozendict(errors)
            return
        disabled_fields = []
        values = ChainMap(provided_values, default_values)
        for field in self.fields.values():
            if (values[field.id] is not None and
                    not field.test_condition(values)):
                if field.id in provided_values:
                    error = ValidationError(
                        "Additional condition not met", 'condition')
                    errors[field.id] = error
                else:
                    disabled_fields.append(field.id)
        if errors:
            self._errors = frozendict(errors)
            return
        # TODO: is second pass necessary if no fields were disabled?
        for name in disabled_fields:
            default_values[name] = None
        for field in self.fields.values():
            if values[field.id] is not None and not field.test_condition(values):
                error = ValidationError(
                    "Additional condition not met", 'condition')
                errors[field.id] = error
        self._errors = frozendict(errors)
        if not errors:
            self._cleaned_data = frozendict(values)

    def __iter__(self):
        return iter(self.fields.values())

    def __getitem__(self, item):
        return self.fields[item]

    def save(self, database, directory=None) -> JobRequest:
        """
        If the form is valid, saves all files and created
        a new job request containing the cleaned input data
        in the database.

        :param database: mongo database instance
        :param directory: save location
        :return: created request
        """
        if not self.is_valid():
            raise RuntimeError(self.errors, 'invalid_form')
        inputs = {}
        for field in self.fields.values():
            value = self.cleaned_data[field.id]
            if isinstance(field, FileField):
                field.save_file(value, database, directory)
            inputs[field.id] = field.to_arg(value)
        request = JobRequest(service=self.service, inputs=inputs)
        request.insert(database)
        return request


FIELD_TYPES = {
    'int': IntegerField,
    'int[]': IntegerArrayField,
    'integer': IntegerField,
    'integer[]': IntegerArrayField,
    'float': DecimalField,
    'float[]': DecimalArrayField,
    'decimal': DecimalField,
    'decimal[]': DecimalArrayField,
    'text': TextField,
    'text[]': TextArrayField,
    'string': TextField,
    'string[]': TextArrayField,
    'boolean': BooleanField,
    'boolean[]': BooleanArrayField,
    'flag': FlagField,
    'flag[]': FlagArrayField,
    'choice': ChoiceField,
    'choice[]': ChoiceArrayField,
    'file': FileField,
    'file[]': FileArrayField
}


class FormLoader(collections.abc.Mapping):
    """
    A helper factory dynamically creating the forms from the configuration.
    Only a single instance of the class is created (subsequent constructor
    calls return the same object) providing a single point where all
    forms can be accessed from.
    """

    def __init__(self):
        self._forms = {}
        self._extra_types = {}

    def read_config(self, service: ServiceConfig) -> Type[BaseForm]:
        attrs = OrderedDict(_service=service.id)
        for key, val in service.parameters.items():
            try:
                attrs[key] = self._build_field(key, val)
            except ValidationError as e:
                msg = f"Failed to load service {service.name}. {e}"
                if e.__cause__ is not None:
                    msg += " %s" % e.__cause__
                raise RuntimeError(msg)
        self._forms[service.id] = cls = DeclarativeFormMetaclass(
            service.id.capitalize() + "Form", (BaseForm,), attrs
        )
        return cls

    def read_dict(self, service_id: str, params: Mapping) -> Type[BaseForm]:
        attrs = OrderedDict(_service=service_id)
        for key, val in params.items():
            try:
                attrs[key] = self._build_field(key, val)
            except ValidationError as e:
                raise RuntimeError(
                    f"Failed to load service. {e} {e.__cause__}"
                )
        self._forms[service_id] = cls = DeclarativeFormMetaclass(
            service_id.capitalize() + "Form", (BaseForm,), attrs
        )
        return cls

    def __getitem__(self, item: str) -> BaseForm:
        """ Retrieve form class by service name. """
        return self._forms[item]

    def __len__(self) -> int:
        return len(self._forms)

    def __iter__(self) -> Iterator[str]:
        return iter(self._forms)

    def _build_field(self, param_id: str, field_dict: dict) -> BaseField:
        """ Constructs a field from the configuration """
        kwargs = {key.replace('-', '_'): val for key, val in field_dict.items()}
        field_type = kwargs.pop('type')
        cls = FIELD_TYPES.get(field_type)
        if cls is None:
            try:
                cls = self._get_custom_field_class(field_type)
                if not issubclass(cls, BaseField):
                    raise TypeError(f"'{cls!r}' do not extend 'BaseField'")
            except (ValueError, AttributeError):
                raise ValueError(f"Invalid field type '{field_type!r}'")
        return cls(param_id, **kwargs)

    def _get_custom_field_class(self, field_type) -> Type[BaseField]:
        """ Imports class that custom type points to. """
        cls = self._extra_types.get(field_type)
        if cls is None:
            if field_type.endswith('[]'):
                base = self._get_custom_field_class(field_type[:-2])
                cls = type(base.__name__ + '[]', (ArrayFieldMixin, base), {})
            else:
                mod, attr = field_type.rsplit('.', 1)
                cls = getattr(import_module(mod), attr)
            self._extra_types[field_type] = cls
        return cls
