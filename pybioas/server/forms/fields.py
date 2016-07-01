import re

from .exceptions import ValidationError


class BaseField:

    def __init__(self, name, default=None):
        """
        Initializes the values of the field and sets the default value.
        :param name: parameter id
        :param default: default value of the field
        :raise ValidationError: default value is not valid
        """
        self._name = name
        if default is not None:
            default = self.validate(default)
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
    def type(self):
        """
        Get the type of the field based on the class name.
        :return: string representation of field type
        """
        return self.__class__.__name__[:-5].lower()

    @property
    def default(self):
        """
        Set `default` as a read-only property.
        :return: default value of the field
        """
        return self._default

    @property
    def required(self):
        return True

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
        Checks if the field has a valid value by calling subclass' `_validate`
        method and catching ValidationError.
        If the validation is successful it sets `_cleaned_value`.
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
        form.
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
        Method validating the field value which has to be overridden in
        more specialised subclasses.
        If the field is valid, this method should return cleaned value;
        otherwise, it raises ValidationError with error description.
        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
        raise NotImplementedError

    def __repr__(self):
        return ("<{} {}: {!r}>"
                .format(self.__class__.__name__, self._name, self.value))


class IntegerField(BaseField):

    def __init__(self, name, default=None, minimum=None, maximum=None):
        """
        :param name: parameter id
        :param default: default value of the field
        :param minimum: minimum accepted value (inclusive)
        :param maximum: maximum accepted value (inclusive)
        """
        self._min = minimum
        self._max = maximum
        super().__init__(name, default)

    def validate(self, value):
        """
        Validates if the field's value can be casted to an integer.
        It check if the value meets minimum and maximum constraints.
        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
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


class DecimalField(BaseField):

    def __init__(self, name, default=None, minimum=None, maximum=None,
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
        super().__init__(name, default)

    def validate(self, value):
        """
        Validates if the value can be casted to a float number and
        meets all constraints.
        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
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


class FileField(BaseField):

    # file name validation: can't start or end with space
    filename_regex = re.compile(r"^[\w\.-](?:[\w \.-]*[\w\.-])?$")

    def __init__(self, name, default=None, mimetype=None, extension=None,
                 max_size=None):
        """
        :param name: parameter id
        :param default: default value of the field
        :param extension: extension the file must have
        :raise ValueError: invalid `max_size` format
        """
        self._mimetype = mimetype
        self._extension = extension
        if max_size is not None:
            match = re.match(r"(\d+)\s*([kMGT]?)B$", max_size)
            if not match:
                raise ValueError("Invalid max_size format %s" % max_size)
            size_val = int(match.group(1))
            size_multiplier = {"": 1, "k": 1024, "M": 1048576, "G": 1073741824,
                               "T": 1099511627776}[match.group(2)]
            max_size = size_val * size_multiplier
        self._max_size = max_size
        super().__init__(name, default)

    def validate(self, value):
        """
        Checks if the filename fits the regular expression and compares checks
        its extension.
        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
        # TODO cleaning converts file id to file path
        match = self.filename_regex.match(value)
        if not match:
            raise ValidationError("name", "Invalid file name.")
        if (self._extension and
                not value.endswith(".%s" % self._extension)):
            raise ValidationError("extension", "Invalid file extension.")
        return value


class TextField(BaseField):

    def __init__(self, name, default=None, min_length=None,
                 max_length=None):
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
        super().__init__(name, default)

    def validate(self, value):
        """
        Checks if the value can be casted to string and checks if the
        length of that string fits into the limits.
        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
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


class BooleanField(BaseField):

    false_literals = {'no', 'false', '0', 'null', 'none'}

    def __init__(self, name, default=None):
        """
        :param name: parameter id
        :param default: default value of the field
        """
        super().__init__(name, default)

    def validate(self, value):
        """
        Compares if the value is one of the string literals indicating false.
        Returns False if so; otherwise evaluates value as a boolean.
        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
        if (type(value) == str and
                value.lower() in self.false_literals):
            cleaned_value = False
        else:
            cleaned_value = bool(value)
        return cleaned_value


class ChoiceField(BaseField):

    def __init__(self, name, default=None, choices=()):
        """
        :param name: parameter id
        :param default: default value of the field
        :param choices: an iterable of allowed choices
        """
        self._choices = list(choices)
        super().__init__(name, default)

    def validate(self, value):
        """
        Checks if the value is one of the specified choices.
        :param value: value to be validated and cleaned
        :return: cleaned value
        :raise ValidationError: field value is invalid
        """
        if value not in self._choices:
            raise ValidationError("choice", "Invalid choice %s." % value)
        else:
            return value

