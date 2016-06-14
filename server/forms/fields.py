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
        return ("<{} {}: {}>"
                .format(self.__class__.__name__, self._id, self.value))


class IntegerField(BaseField):

    def _validate(self):
        """
        Validates if the field value can be casted to an integer.
        :return: whether the field's value has an integer representation
        """
        try:
            self._cleaned_value = int(self.value)
        except (ValueError, TypeError):
            return False
        return True


class DecimalField(BaseField):

    def _validate(self):
        """
        Validates if the value can be casted to a decimal number.
        :return: whether the value is a correct decimal
        """
        try:
            self._cleaned_value = float(self.value)
        except (ValueError, TypeError):
            return False
        return True


class FileField(BaseField):

    # file name validation: can't start or end with space
    filename_regex = re.compile(r"^[\w\.-](?:[\w \.-]*[\w\.-])?$")

    def _validate(self):
        """
        Checks if the value is a valid file name and sets it to `_cleaned_data`
        :return: if the value is a correct file name
        """
        match = self.filename_regex.match(self.value)
        self._cleaned_value = match and match.group()
        return bool(match)


class TextField(BaseField):

    def _validate(self):
        """
        Checks if the object has a string representation and sets it to the
        `_cleaned_value`.
        :return: whether the object has a string representation
        """
        try:
            self._cleaned_value = str(self.value)
            return True
        except TypeError:
            return False


class BooleanField(BaseField):

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

    def __init__(self, option_id, choices, default=None):
        """
        :param choices: an iterable of allowed choices
        :param default: default value of the field
        """
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
