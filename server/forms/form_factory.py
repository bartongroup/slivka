from copy import deepcopy
from lxml import etree

from db.models import Request, Option
from .exceptions import ValidationError
from .fields import (IntegerField, DecimalField, FileField, TextField,
                     BooleanField, SelectField)


class BaseForm:

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
            raise ValidationError
        return {
            field.id: field.cleaned_value
            for field in self.fields
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
                option_id=field.id,
                type=field.type,
                value=field.cleaned_value
            )
            for field in self.fields
        ]
        session.add(request)

    def to_dict(self):
        return {
            "fields": [
                {
                    "id": opt_id,
                    "type": field.type,
                    "required": field.required,
                    "default": field.default
                }
                for opt_id, field in self._fields.items()
            ]
        }

    def __repr__(self):
        return "<{}> bound={}".format(self.__class__.__name__, self._bound)


class FormFactory:

    field_classes = {
        "integer": IntegerField,
        "decimal": DecimalField,
        "file": FileField,
        "text": TextField,
        "boolean": BooleanField,
        "select": SelectField
    }

    @staticmethod
    def get_form_class(form_name, service, param_file):
        """
        Constructs a form class from a parameters configuration file
        :param form_name: name given to a new form class
        :param service: service name the form is bound to
        :param param_file: a path to xml file describing form fields
        :return: new BaseForm subclass with fields loaded from the param file
        """
        xml_tree = FormFactory._validate_param_file(param_file)
        fields = FormFactory._load_fields(xml_tree)
        return type(
            form_name, (BaseForm, ),
            {"_fields": dict(fields), "_service": service}
        )

    @staticmethod
    def _validate_param_file(param_file):
        """
        Validates parameters file against the parameter schema and parses the
        document into an element tree
        :param param_file: path or a file-like object to parameters file
        :return: parsed document as an element tree
        :raise ValueError: parameter file is invalid
        """
        xmlschema = etree.XMLSchema(file="./config/ParameterConfigSchema.xsd")
        xml_parser = etree.XMLParser(remove_blank_text=True)
        xml_tree = etree.parse(param_file, parser=xml_parser)
        if not xmlschema.validate(xml_tree):
            raise ValueError("Specified parameter file is invalid")
        else:
            return xml_tree

    @staticmethod
    def _load_fields(xml_tree):
        """
        Loads the list of form fields from the xml tree.
        :param xml_tree: service parameter description element tree
        :return: iterable of field objects
        """
        runner_config = xml_tree.getroot()
        for option_element in runner_config:
            yield FormFactory._parse_option_element(option_element)

    @staticmethod
    def _parse_option_element(element):
        """
        Parses the option tan and constructs Field from ir
        :param element: xml node of option element
        :return: BaseField's subclass according to the value type
        """
        opt_id = element.get("id")
        select = element.find("select")

        if select is None:
            value_element = element[3]  # vulnerable part, crashes on comments
            value_type = value_element.tag[:-5]
            kwargs = {
                "default": value_element.findtext("default")
            }
            if value_type == "integer":
                minimum = value_element.findtext("min")
                if minimum is not None:
                    kwargs["minimum"] = int(minimum)
                maximum = value_element.findtext("max")
                if maximum is not None:
                    kwargs["maximum"] = int(maximum)
            elif value_type == "decimal":
                min_inclusive = value_element.findtext("minInclusive")
                if min_inclusive is not None:
                    kwargs["min_inclusive"] = float(min_inclusive)
                min_exclusive = value_element.findtext("minExclusive")
                if min_exclusive is not None:
                    kwargs["min_exclusive"] = float(min_exclusive)
                max_inclusive = value_element.findtext("maxInclusive")
                if max_inclusive is not None:
                    kwargs["max_inclusive"] = float(max_inclusive)
                max_exclusive = value_element.findtext("maxExclusive")
                if max_exclusive is not None:
                    kwargs["max_exclusive"] = float(max_exclusive)
            elif value_type == "file":
                kwargs["extension"] = value_element.findtext("extension")
            elif value_type == "text":
                min_length = value_element.findtext("minLength")
                if min_length is not None:
                    kwargs["min_length"] = int(min_length)
                max_length = value_element.findtext("maxLength")
                if max_length is not None:
                    kwargs["max_length"] = int(max_length)
            field_class = FormFactory.field_classes[value_type]
            return opt_id, field_class(opt_id, **kwargs)
        else:
            choices = [choice_el.findtext("param") for choice_el in select]
            return opt_id, SelectField(opt_id, choices=choices)
