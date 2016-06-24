import os.path
from lxml import etree

from settings import BASE_DIR


def validate_form_file(form_file):
    """
    Validates parameters file against the parameter schema and parses the
    document into an element tree
    :param form_file: path or a file-like object to form description file
    :return: parsed document as an element tree
    :raise ValueError: parameter file is invalid
    """
    schema_file = os.path.join(BASE_DIR, "utils", "FormSchema.xsd")
    xml_schema = etree.XMLSchema(file=schema_file)
    xml_parser = etree.XMLParser(remove_blank_text=True)
    xml_tree = etree.parse(form_file, parser=xml_parser)
    if not xml_schema.validate(xml_tree):
        raise ValueError("Form description is invalid.")
    else:
        return xml_tree
