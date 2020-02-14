from collections import OrderedDict
from tempfile import mkstemp

import itertools
import typing
from functools import partial
from werkzeug.datastructures import FileStorage, MultiDict

import slivka
import slivka.db
from slivka.server.forms.file_validators import validate_file_content
from slivka.utils import cached_property
from .file_proxy import FileProxy, _get_file_from_uuid
from .widgets import *

__all__ = [
    'BaseField',
    'IntegerField',
    'DecimalField',
    'TextField',
    'BooleanField',
    'FlagField',
    'ChoiceField',
    'FileField',
    'ValidationError'
]

EMPTY_VALUES = ({}, set(), [], (), None, '')


class BaseField:
    def __init__(self,
                 name,
                 label='',
                 description='',
                 default=None,
                 required=True,
                 multiple=False):
        self.name = name
        self.label = label
        self.description = description
        self.default = default
        self.required = required
        self.multiple = multiple
        self._widget = None

    def value_from_request_data(self, data: MultiDict, files: MultiDict):
        """
        Retrieve raw value from the request data.
        The same value will be further passed to `validate` method

        :param data: request POST data
        :param files: request multipart-POST files
        :return:
        """
        if self.multiple:
            return data.getlist(self.name)
        else:
            return data.get(self.name)

    def run_validation(self, value):
        """ Run validation and return converted value. """
        if value in EMPTY_VALUES:
            return None
        else:
            return value

    def validate(self, value):
        if not self.multiple:
            value = self.run_validation(value)
            if value is None:
                if self.default is not None:
                    return self.default
                elif self.required:
                    raise ValidationError("Field is required", 'required')
            return value
        else:
            if not value:
                if self.default is not None:
                    return [self.default]
                elif self.required:
                    raise ValidationError("Field is required", 'required')
            return [self.run_validation(v) for v in value]

    def _validate_default(self):
        if self.default is not None:
            try:
                self.run_validation(self.default)
            except ValidationError as e:
                raise RuntimeError("Invalid default value") from e

    def serialize_value(self, value):
        if self.multiple:
            return [self.to_cmd_parameter(val) for val in value]
        else:
            return self.to_cmd_parameter(value)

    def to_cmd_parameter(self, value):
        return value

    def __json__(self):
        return {
            'name': self.name,
            'label': self.label,
            'description': self.description or "",
            'required': self.required,
            'multiple': self.multiple,
            'default': self.default
        }

    @property
    def widget(self):
        raise NotImplementedError

    @property
    def input_tag(self):
        return self.widget.render()


class IntegerField(BaseField):
    # noinspection PyShadowingBuiltins
    def __init__(self,
                 name,
                 min=None,
                 max=None,
                 **kwargs):
        super().__init__(name, **kwargs)
        self.__validators = []
        self.min = min
        self.max = max
        if max is not None:
            self.__validators.append(partial(_max_value_validator, max))
        if min is not None:
            self.__validators.append(partial(_min_value_validator, min))
        self._validate_default()

    @property
    def widget(self):
        if self._widget is None:
            widget = NumberInputWidget(self.name)
            widget['min'] = self.min
            widget['max'] = self.max
            widget['value'] = self.default
            widget['required'] = self.required
            self._widget = widget
        return self._widget

    def run_validation(self, value):
        value = super().run_validation(value)
        if value is None:
            return None
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValidationError("Invalid integer value", 'invalid')
        for validator in self.__validators:
            validator(value)
        return value

    def __json__(self):
        j = super().__json__()
        j['type'] = 'integer'
        if self.min is not None: j['min'] = self.min
        if self.max is not None: j['max'] = self.max
        return j


class DecimalField(BaseField):
    # noinspection PyShadowingBuiltins
    def __init__(self,
                 name,
                 min=None,
                 max=None,
                 min_exclusive=False,
                 max_exclusive=False,
                 **kwargs):
        super().__init__(name, **kwargs)
        self.__validators = []
        self.min = min
        self.max = max
        self.min_exclusive = min_exclusive
        self.max_exclusive = max_exclusive
        if max is not None:
            validator = (_exclusive_max_value_validator
                         if max_exclusive else _max_value_validator)
            self.__validators.append(partial(validator, max))
        if min is not None:
            validator = (_exclusive_min_value_validator
                         if min_exclusive else _min_value_validator)
            self.__validators.append(partial(validator, min))
        self._validate_default()

    @property
    def widget(self):
        if self._widget is None:
            widget = NumberInputWidget(self.name)
            widget['min'] = self.min
            widget['max'] = self.max
            widget['value'] = self.default
            widget['required'] = self.required
            self._widget = widget
        return self._widget

    def run_validation(self, value):
        value = super().run_validation(value)
        if value is None:
            return None
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValidationError("Invalid decimal number", 'invalid')
        for validator in self.__validators:
            validator(value)
        return value

    def __json__(self):
        j = super().__json__()
        j['type'] = 'decimal'
        if self.max is not None: j['max'] = self.max
        if self.min is not None: j['min'] = self.min
        if self.min_exclusive is not None: j['minExclusive'] = self.min_exclusive
        if self.max_exclusive is not None: j['maxExclusive'] = self.max_exclusive
        return j


class TextField(BaseField):
    def __init__(self,
                 name,
                 min_length=None,
                 max_length=None,
                 **kwargs):
        super().__init__(name, **kwargs)
        self.__validators = []
        self.min_length = min_length
        self.max_length = max_length
        if min_length is not None:
            self.__validators.append(partial(
                _min_length_validator, min_length
            ))
        if max_length is not None:
            self.__validators.append(partial(
                _max_length_validator, max_length
            ))
        self._validate_default()

    @property
    def widget(self):
        if self._widget is None:
            self._widget = TextInputWidget(self.name)
            self._widget['value'] = self.default
            self._widget['required'] = self.required
        return self._widget

    def run_validation(self, value):
        value = super().run_validation(value)
        if value is None:
            return None
        value = str(value)
        for validator in self.__validators:
            validator(value)
        return value

    def __json__(self):
        j = super().__json__()
        j['type'] = 'text'
        if self.min_length is not None: j['minLength'] = self.min_length
        if self.max_length is not None: j['maxLength'] = self.max_length
        return j


class BooleanField(BaseField):
    FALSE_STR = {'no', 'false', '0', 'n', 'f', 'none', 'null', 'off'}

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self._validate_default()

    @property
    def widget(self):
        if self._widget is None:
            self._widget = CheckboxInputWidget(self.name, value='true')
            self._widget['checked'] = bool(self.default)
            self._widget['required'] = self.required
        return self._widget

    def run_validation(self, value):
        value = super().run_validation(value)
        if isinstance(value, str) and value.lower() in self.FALSE_STR:
            value = False
        return True if value else None

    def __json__(self):
        j = super().__json__()
        j['type'] = 'boolean'
        return j


FlagField = BooleanField


class ChoiceField(BaseField):
    def __init__(self,
                 name,
                 choices=(),
                 **kwargs):
        super().__init__(name, **kwargs)
        self.__validators = []
        self.choices = OrderedDict(choices)
        self.__validators.append(partial(
            _choice_validator,
            list(itertools.chain(self.choices.keys(), self.choices.values()))
        ))
        self._validate_default()

    @property
    def widget(self):
        if self._widget is None:
            self._widget = SelectWidget(self.name, options=self.choices)
            self._widget['required'] = self.required
            self._widget['multiple'] = self.multiple
        return self._widget

    def run_validation(self, value):
        value = super().run_validation(value)
        if value is None:
            return None
        if value not in self.choices.keys() and value not in self.choices.values():
            raise ValidationError(
                "Value \"%s\" is not one of the available choices." % value,
                'invalid'
            )
        return value

    def to_cmd_parameter(self, value):
        return self.choices.get(value, value)

    def __json__(self):
        j = super().__json__()
        j['type'] = 'choice'
        j['choices'] = list(self.choices)
        return j


class FileField(BaseField):
    def __init__(self,
                 name,
                 media_type=None,
                 media_type_parameters=(),
                 extensions=(),
                 **kwargs):
        assert kwargs.get('default') is None
        super().__init__(name, **kwargs)
        self.__validators = []
        self.extensions = extensions
        self.media_type = media_type
        self.media_type_parameters = media_type_parameters or {}
        if media_type is not None:
            self.__validators.append(partial(
                _media_type_validator, media_type
            ))

    save_location = cached_property(lambda self: slivka.settings.uploads_dir)

    def value_from_request_data(self, data: MultiDict, files: MultiDict):
        if self.multiple:
            return files.getlist(self.name) + data.getlist(self.name)
        else:
            return files.get(self.name) or data.get(self.name)

    @property
    def widget(self):
        if self._widget is None:
            widget = FileInputWidget(self.name)
            widget['accept'] = str.join(
                ',', ('.%s' % ext for ext in self.extensions)
            )
            self._widget = widget
        return self._widget

    def run_validation(self, value) -> typing.Optional['FileProxy']:
        value = super().run_validation(value)
        if value is None:
            return None
        elif isinstance(value, FileStorage):
            file = FileProxy(file=value)
        elif isinstance(value, str):
            file = _get_file_from_uuid(value, slivka.db.database)
            if file is None:
                raise ValidationError(
                    "A file with given uuid not found", 'not_found'
                )
        elif isinstance(value, FileProxy):
            file = value
        else:
            raise TypeError("Invalid type %s" % type(value))
        for validator in self.__validators:
            validator(file)
        return file

    def __json__(self):
        j = super().__json__()
        j['type'] = 'file'
        if self.media_type is not None:
            j['mimetype'] = self.media_type
            j['mediaType'] = self.media_type
            j['mediaTypeParameters'] = self.media_type_parameters
        if self.extensions: j['extensions'] = self.extensions
        return j

    def to_cmd_parameter(self, value: 'FileProxy'):
        if not value: return None
        if value.path is None:
            (fd, path) = mkstemp(dir=self.save_location)
            with open(fd, 'wb') as fp:
                value.save_as(path=path, fp=fp)
        return value.path


def _max_value_validator(limit, value):
    if value > limit:
        raise ValidationError(
            "Value must be less than or equal to %s" % limit, 'max_value'
        )


def _min_value_validator(limit, value):
    if value < limit:
        raise ValidationError(
            "Value must be greater than or equal to %s" % limit, 'min_value'
        )


def _exclusive_max_value_validator(limit, value):
    if value >= limit:
        raise ValidationError(
            "Value must be less than %s" % limit, 'max_value'
        )


def _exclusive_min_value_validator(limit, value):
    if value <= limit:
        raise ValidationError(
            "Value must be greater than %s" % limit, 'min_value'
        )


def _min_length_validator(limit, value):
    if len(value) < limit:
        raise ValidationError(
            "Value is too short. Min %d characters" % limit, 'min_length'
        )


def _max_length_validator(limit, value):
    if len(value) > limit:
        raise ValidationError(
            "Value is too long. Max %d characters" % limit, 'max_length'
        )


def _choice_validator(choices, value):
    if value not in choices:
        raise ValidationError(
            "Value \"%s\" is not one of the available choices." % value,
            'invalid'
        )


def _media_type_validator(media_type, file: FileProxy):
    file.reopen()
    if not validate_file_content(file, media_type):
        raise ValidationError(
            "This media type is not accepted", 'media_type'
        )


class ValidationError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message, code)
        self.message = message
        self.code = code
