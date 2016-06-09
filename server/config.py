import configparser

from lxml import etree


services_config = configparser.ConfigParser()
services_config.read('./config/services.ini')

services = services_config.sections()


class ServiceInfo:

    def __init__(self, param_file):
        xml_tree = self._validate_param_file(param_file)
        self._load_options(xml_tree)

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

    def _load_options(self, xml_tree):
        """
        Loads the list of options from an xml tree
        :param xml_tree: source zml tree
        """
        runner_config = xml_tree.getroot()
        self.options = [
            self._parse_option_element(opt_el)
            for opt_el in runner_config
        ]

    @staticmethod
    def _parse_option_element(element):
        """
        Parses the option tree element and constructs an option object
        :param element: option tree element
        """
        option = {
            "id": element.get("id"),
            "name": element.find("name").text,
            "value": {}
        }
        select = element.find("select")

        if select is None:
            # param and value pair
            option["param"] = element.find("param").text
            value_element = element[3]
            option["value"]["type"] = value_element.tag[:-5]
            option["value"].update(
                {el.tag: el.text for el in value_element}
            )
        else:
            option["value"]["type"] = "select"
            option["value"]["choices"] = []
            for choice in select:
                description = choice.find("description")
                name = choice.find("name").text
                option["value"]["choices"].append({
                    "name": name,
                    "param": choice.find("param").text,
                    "description": (description.text
                                    if description is not None else None)
                })
        return option


service_info = {
    name: ServiceInfo(services_config.get(name, 'parameters'))
    for name in services
}
