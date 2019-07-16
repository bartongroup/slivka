import os
import re

import sqlalchemy.orm.exc

from slivka.db import start_session, models
from .exceptions import ValidationError


class BaseField:
    """Base class for all form fields.

    :param name: parameter id
    :param default: default value of the field
    :raise ValidationError: default value is not valid
    """
    def __init__(self, name, label='', description='',
                 default=None, required=True):
        """
        Initializes the values of the field and sets the default value.

        :param name: parameter id
        :param default: default value of the field
        :raise ValidationError: default value is not valid
        """
        self._name = name
        self._label = label
        self._description = description
        self._required = required
        if default is not None:
            try:
                self.validate(default)
            except ValidationError as e:
                raise RuntimeError('Invalid default in field %s' % name) from e
        self._default = default
        self._value = None
        self._cleaned_value = None
        self._error = None
        self._valid = None

    @property
    def name(self):
        """
        :return: option id
        """
        return self._name

    @property
    def label(self):
        return self._label

    @property
    def description(self):
        return self._description

    @property
    def type(self):
        """
        Get the type of the field based on the class name.

        :return: string representation of field type
        """
        return self.__class__.__name__[:-5].lower()

    @property
    def default(self):
        """
        Make `default` as a read-only property.

        :return: default value of the field
        """
        return self._default

    @property
    def required(self):
        return self._required

    @property
    def constraints(self):
        return [
            {"name": name, "value": value}
            for (name, value) in self.get_constraints_list()
            if value is not None
        ]

    def get_constraints_list(self):
        return []

    @property
    def value(self):
        """
        Returns field's value. If it wasn't set yet then returns default value.

        :return: value assigned to the field or default.
        """
        if self._value is None:
            return self._default
        else:
            return self._value

    @value.setter
    def value(self, value):
        """
        Sets the value of the field and invalidates it.

        :param value: new value of the field
        """
        self._value = value
        self._valid = None

    @property
    def error(self):
        if self._valid is False:
            return self._error
        else:
            return None

    @property
    def is_valid(self):
        """
        Checks if the field has a valid value by calling subclass'
        ``validate`` method and catching the ValidationError.
        If the validation is successful it sets ``_cleaned_value`` to the
        value returned by ``validate``.

        :return: whether the field is valid
        """
        if self._valid is None:
            try:
                self._cleaned_value = self.validate(self.value)
            except ValidationError as e:
                self._error = e
                self._valid = False
            else:
                self._valid = True
        return self._valid

    @property
    def cleaned_value(self):
        """
        Returns the value of the field after casting it into an appropriate
        format.

        :return: cleaned field value
        :raise ValidationError: form is not valid
        """
        if self.is_valid:
            return self._cleaned_value
        else:
            assert self._error, "Exception was not saved."
            raise self._error

    def validate(self, value):
        """
        Method validating the field value which should be overridden in
        more specialised subclasses.
        If the field is valid, this method should return cleaned value;
        otherwise, it raises ValidationError with error description.

        Default behaviour checks if the field is required and raises an
        exception when the field value is not provided.

        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
        if value is None and self.required:
            raise ValidationError("required", "This field is required")
        return value

    def __repr__(self):
        return ("<{} {}: {!r}>"
                .format(self.__class__.__name__, self._name, self.value))


class IntegerField(BaseField):
    def __init__(self, name, label='', description='',
                 default=None, required=True, minimum=None, maximum=None):
        """
        :param name: parameter id
        :param default: default value of the field
        :param minimum: minimum accepted value (inclusive)
        :param maximum: maximum accepted value (inclusive)
        """
        self._min = minimum
        self._max = maximum
        super().__init__(name=name, label=label, description=description,
                         default=default, required=required)

    def validate(self, value):
        """
        Extends the default behaviour checking if the field's value can be
        casted to an integer and if the value meets minimum and maximum
        constraints.

        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
        value = super().validate(value)
        if value is None:
            return None
        try:
            cleaned_value = int(value)
        except (ValueError, TypeError):
            raise ValidationError("type", "Not a valid integer.")
        if self._min is not None and cleaned_value < self._min:
            raise ValidationError(
                "min", "Value must be greater than %d." % self._min
            )
        if self._max is not None and cleaned_value > self._max:
            raise ValidationError(
                "max", "Value must be less than %d." % self._max
            )
        return cleaned_value

    def get_constraints_list(self):
        return [
            ("min", self._min),
            ("max", self._max)
        ]


class DecimalField(BaseField):
    def __init__(self, name, label='', description='', required=True,
                 default=None, minimum=None, maximum=None,
                 min_exclusive=False, max_exclusive=False):
        """
        Sets the field and its constraints.
        Inclusive and exclusive limits are mutually exclusive and at least
        one in each pair must be None.

        :param name: parameter id
        :param default: default value of the field
        :param minimum: minimum accepted value
        :param maximum: maximum accepted value
        :param min_exclusive: whether minimum value is exclusive
        :param max_exclusive: whether maximum value is exclusive
        """
        self._min = (minimum, min_exclusive)
        self._max = (maximum, max_exclusive)
        super().__init__(name=name, label=label, description=description,
                         default=default, required=required)

    def validate(self, value):
        """
        Extends the default behaviour checking if the value can be cast to
        float and meets all value constraints.

        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
        value = super().validate(value)
        if value is None:
            return None
        try:
            cleaned_value = float(value)
        except (ValueError, TypeError):
            raise ValidationError("type", "Not a valid decimal.")
        if self._min[0] is not None:
            if self._min[1]:
                # cleaned value should be > minimum
                if cleaned_value <= self._min[0]:
                    raise ValidationError(
                        "min",
                        "Value must be less or equal to %d." % self._min[0]
                    )
            else:
                # cleaned value should be >= minimum
                if cleaned_value < self._min[0]:
                    raise ValidationError(
                        "min",
                        "Value must be less than %d." % self._min[0]
                    )
        if self._max[0] is not None:
            if self._max[1]:
                # cleaned value should be < maximum
                if cleaned_value >= self._max[0]:
                    raise ValidationError(
                        "max",
                        "Value must be greater or equal to %d." % self._max[0]
                    )
            else:
                # cleaned value should be < maximum
                if cleaned_value > self._max[0]:
                    raise ValidationError(
                        "max",
                        "Value must be greater than %d." % self._max[0]
                    )
        return cleaned_value

    def get_constraints_list(self):
        return [
            ("min", self._min[0]),
            ("min_exclusive", bool(self._min[1])),
            ("max", self._max[0]),
            ("max_exclusive", bool(self._max[1]))
        ]


class FileField(BaseField):
    size_multiplier = {
        "": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4
    }

    def __init__(self, name, label='', description='', default=None,
                 required=True, mimetype=None, extension=None, max_size=None):
        """
        :param name: parameter id
        :param default: default value of the field
        :param extension: extension the file must have
        :raise ValueError: invalid `max_size` format
        """
        self._mimetype = mimetype
        self._extension = extension
        if max_size is not None:
            match = re.match(r"(\d+)\s*([KMGT]?)B$", max_size)
            if not match:
                raise ValueError("Invalid max_size format %s" % max_size)
            size_val = int(match.group(1))
            max_size = size_val * self.size_multiplier[match.group(2)]
        self._max_size = max_size
        super().__init__(name=name, label=label, description=description,
                         default=default, required=required)

    def validate(self, value):
        """
        Extends the default behaviour checking if the file with a given id is
        registered in the database and the path to that file exists.
        Validation converts file id to the actual file path in the filesystem.

        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
        value = super().validate(value)
        if value is None:
            return None
        file = None
        with start_session() as session:
            try:
                file = (session.query(models.File)
                        .filter(models.File.uuid == value)
                        .one())
            except sqlalchemy.orm.exc.NoResultFound:
                raise ValidationError("file", "File does not exist.")
        if not os.path.exists(file.path):
            raise ValidationError("file", "File does not exist.")
        # TODO check againts mimetype and maxsize
        # TODO drop support for extension as it is irrelevant
        return file.path

    def get_constraints_list(self):
        return [
            ("mimetype", self._mimetype),
            ("extension", self._extension),
            ("max_size", self._max_size)
        ]


class TextField(BaseField):
    def __init__(self, name, label='', description='', default=None,
                 required=True, min_length=None, max_length=None):
        """
        :param name: parameter id
        :param default: default value of the field
        :param min_length: minimum length of the string
        :param max_length: maximum length of the string
        :raise ValueError: length constraint is negative
        :raise ValueError: maximum limit is lower than minimum limit
        """
        if ((min_length is not None and min_length < 0) or
                (max_length is not None and max_length < 0)):
            raise ValueError("Length can't be negative")
        if (min_length is not None and
            max_length is not None and
                min_length > max_length):
            raise ValueError("Maximum length must be greater than minimum "
                             "length")
        self._min_length = min_length
        self._max_length = max_length
        super().__init__(name=name, label=label, description=description,
                         default=default, required=required)

    def validate(self, value):
        """
        Extends the default behaviour checking if the value can be cast to
        string and the length of that string fits into the limits.

        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
        value = super().validate(value)
        if value is None:
            return None
        try:
            cleaned_value = str(value)
        except TypeError:
            raise ValidationError(
                "type",
                "Value has no string representation."
            )
        if (self._min_length is not None and
                len(cleaned_value) < self._min_length):
            raise ValidationError(
                "min_length",
                "Value is too short (min %d)." % self._min_length
            )
        if (self._max_length is not None and
                len(cleaned_value) > self._max_length):
            raise ValidationError(
                "max_length",
                "Value is too long (max %d)." % self._max_length
            )
        return cleaned_value

    def get_constraints_list(self):
        return [
            ("min_length", self._min_length),
            ("max_length", self._max_length)
        ]


class BooleanField(BaseField):
    false_literals = {'no', 'false', '0', 'null'}

    def __init__(self, name, label='', description='', default=None,
                 required=True):
        """
        :param name: parameter id
        :param default: default value of the field
        """
        super().__init__(name=name, label=label, description=description,
                         default=default, required=required)

    def validate(self, value):
        """
        Extends the default behaviour validating boolean values.
        If the value is one of the string literals indicating false returns
        False; otherwise evaluates the value as a boolean.

        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
        value = super().validate(value)
        if (type(value) == str and
                value.lower() in self.false_literals):
            value = False
        value = bool(value)
        if not value and self.required:
            raise ValidationError("required", "This field is required")
        return value or None


class ChoiceField(BaseField):
    def __init__(self, name, label='', description='',
                 default=None, required=True, choices=None):
        """
        :param required:
        :param name: parameter id
        :param default: default value of the field
        :param choices: an iterable of allowed choices
        """
        if choices is None:
            choices = {}
        self._choices = choices
        super().__init__(name=name, label=label, description=description,
                         default=default, required=required)

    def validate(self, value):
        """
        Extends the default behaviour checking if the selected value is one of
        the available choices. If so, return value assigned to that choice,
        if ``None`` and the field is not required return ``None``, otherwise
        raise a ``ValidationError``.

        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
        value = super().validate(value)
        if not(value in self._choices.keys() or value is None):
            raise ValidationError("choice", "Invalid choice %s." % value)
        else:
            return self._choices.get(value)

    def get_constraints_list(self):
        return [
            ("choices", list(self.choices))
        ]

    @property
    def choices(self):
        return self._choices.keys()
