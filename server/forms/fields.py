import re

from .exceptions import ValidationError


class BaseField:

    def __init__(self, option_id, default=None):
        """
        Initializes the values of the field and sets the default value.
        :param default: default value of the field
        """
        self._id = option_id
        self._default = default
        self._value = None
        self._cleaned_value = None
        self._valid = None

    @property
    def id(self):
        """
        :return: option id
        """
        return self._id

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
    def is_valid(self):
        """
        Checks if the field has a valid value by calling subclass' `_validate`
        method.
        :return: whether the field is valid
        """
        if self._valid is None:
            self._valid = self._validate()
        return self._valid

    @property
    def cleaned_value(self):
        """
        Returns the value of the field after casting it into an appropriate
        form.
        :return: cleaned field value
        :raise ValueError: form is not valid
        """
        if self.is_valid:
            return self._cleaned_value
        else:
            raise ValidationError

    def _validate(self):
        """
        Method validating the field value which has to be overridden in
        more specialised subclasses.
        If the field is valid, this method should set the value of
        `_cleaned_value` attribute. For invalid field, this attribute is
        undefined.
        :return: whether the field value is valid
        """
        raise NotImplementedError

    def __repr__(self):
        return ("<{} {}: {!r}>"
                .format(self.__class__.__name__, self._id, self.value))


class IntegerField(BaseField):

    def __init__(self, option_id, default=None, minimum=None, maximum=None):
        try:
            default = int(default)
        except (TypeError, ValueError):
            raise AssertionError("Default is not an integer")
        super().__init__(option_id, default)
        self._min = minimum
        self._max = maximum

    def _validate(self):
        """
        Validates if the field value can be casted to an integer.
        :return: whether the field's value has an integer representation
        """
        try:
            cleaned_value = int(self.value)
        except (ValueError, TypeError):
            return False
        if self._min is not None and cleaned_value < self._min:
            return False
        if self._max is not None and cleaned_value > self._max:
            return False
        self._cleaned_value = cleaned_value
        return True


class DecimalField(BaseField):

    def __init__(self, option_id, default=None, min_inclusive=None,
                 min_exclusive=None, max_inclusive=None, max_exclusive=None):
        try:
            default = float(default)
        except (TypeError, ValueError):
            raise AssertionError("Default is not a decimal")
        super().__init__(option_id, default)
        if not (min_inclusive is None or min_exclusive is None):
            raise ValueError("You can't specify inclusive and exclusive "
                             "minimum at the same time")
        if not (max_inclusive is None or max_inclusive is None):
            raise ValueError("You can't specify inclusive and exclusive "
                             "maximum at the same time")

        if min_inclusive is not None:
            self._min = (min_inclusive, True)
        elif min_exclusive is not None:
            self._min = (min_exclusive, False)
        else:
            self._min = None

        if max_inclusive is not None:
            self._max = (max_inclusive, True)
        elif max_exclusive is not None:
            self._max = (max_exclusive, False)
        else:
            self._max = None

    def _validate(self):
        """
        Validates if the value can be casted to a decimal number.
        :return: whether the value is a correct decimal
        """
        try:
            cleaned_value = float(self.value)
        except (ValueError, TypeError):
            return False
        if self._min:
            if self._min[1]:
                # cleaned value should be >= minimum
                if cleaned_value < self._min[0]:
                    return False
            else:
                # cleaned value should be > minimum
                if cleaned_value <= self._min[0]:
                    return False
        if self._max:
            if self._max[1]:
                # cleaned value should be <= maximum
                if cleaned_value > self._max[0]:
                    return False
            else:
                # cleaned value should be < maximum
                if cleaned_value >= self._max[0]:
                    return False
        self._cleaned_value = cleaned_value
        return True


class FileField(BaseField):

    # file name validation: can't start or end with space
    filename_regex = re.compile(r"^[\w\.-](?:[\w \.-]*[\w\.-])?$")

    def __init__(self, option_id, default=None, extension=None):
        super().__init__(option_id, default)
        self._extension = extension

    def _validate(self):
        """
        Checks if the value is a valid file name and sets it to `_cleaned_data`
        :return: if the value is a correct file name
        """
        match = self.filename_regex.match(self.value)
        if not match:
            return False
        cleaned_value = match.group()
        if (self._extension and
                not cleaned_value.endswith(".%s" % self._extension)):
            return False
        self._cleaned_value = cleaned_value
        return True


class TextField(BaseField):

    def __init__(self, option_id, default=None, min_length=None,
                 max_length=None):
        super().__init__(option_id, default)
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

    def _validate(self):
        """
        Checks if the object has a string representation and sets it to the
        `_cleaned_value`.
        :return: whether the object has a string representation
        """
        try:
            cleaned_value = str(self.value)
        except TypeError:
            return False
        if (self._min_length is not None and
                len(cleaned_value) < self._min_length):
            return False
        if (self._max_length is not None and
                len(cleaned_value) > self._max_length):
            return False
        self._cleaned_value = cleaned_value
        return True


class BooleanField(BaseField):

    def __init__(self, option_id, default):
        if (type(default) == str and
                default.lower() in {'no', 'false', '0', 'null', 'none'}):
            default = False
        else:
            default = bool(default)
        super().__init__(option_id, default)

    def _validate(self):
        """
        Checks if the value is one of the "false" words and sets the
        `_cleaned_value` to False. Otherwise, value is evaluated as a boolean.
        :return: True (every object is a valid boolean)
        """
        if (type(self.value) == str and
                self.value.lower() in {'no', 'false', '0', 'null', 'none'}):
            self._cleaned_value = False
        else:
            self._cleaned_value = bool(self.value)
        return True


class SelectField(BaseField):

    def __init__(self, option_id, default=None, choices=()):
        """
        :param choices: an iterable of allowed choices
        :param default: default value of the field
        """
        assert default is None or default in choices, "Invalid default choice"
        super().__init__(option_id, default)
        self._choices = choices

    def _validate(self):
        """
        Checks if the value is one of the choices and sets `_cleaned_value`
        to it.
        :return: whether the value is a valid choice
        """
        if self.value in self._choices:
            self._cleaned_value = self.value
            return True
        else:
            return False
