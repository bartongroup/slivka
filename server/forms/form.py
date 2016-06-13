from lxml import etree

from .fields import (IntegerField, DecimalField, FileField, TextField,
                     BooleanField, SelectField)


class BaseForm:

    _fields = {}
    _service = None

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
        return self._fields.values()

    def is_valid(self):
        """
        Checks if the form and its fields are valid.
        :return: whether the form is valid
        """
        if self._is_valid is None:
            self._is_valid = all(field.is_valid for field in self.fields)
        return self._is_valid

    def save(self):
        """
        Saves the form data to the database as a new task request
        """
        raise NotImplementedError

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
        :param form_name:
        :param service:
        :param param_file:
        :return:
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
            default_element = value_element.find("default")
            if default_element is None:
                default = None
            else:
                default = default_element.text
            field_class = FormFactory.field_classes[value_type]
            return opt_id, field_class(default=default)
        else:
            choices = [choice_el.findtext("param") for choice_el in select]
            return opt_id, SelectField(choices)
