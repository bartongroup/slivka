#!usr/bin/env

import argparse
import json
import os.path
import string

from lxml import etree


class CommandRunner(object):
    def __init__(self, param_file, values=None):
        xml_tree = self._validate_param_file(param_file)
        self._load_options(xml_tree)
        if values is not None:
            self.set_values(values)

    @staticmethod
    def _validate_param_file(param_file):
        """
        Validates parameters file agaist the parameter schema and parses the
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
        self.options = [CommandOption(opt_el) for opt_el in runner_config]

    def get_options(self):
        """
        :return: the list of options
        """
        return self.options

    def set_values(self, values):
        """
        Sets values to the option parameters
        :param values: a dictionary of option values
        """
        for option in self.options:
            option.value = values.get(option.id)

    def run_command(self):
        """
        Runs a command with specified set of options.
        """
        pass

    def build_command(self):
        """
        Builds a command line joining all command options.
        :return: full command line of parameters
        """
        command_args = [option.get_command_option() for option in self.options]
        return " ".join(filter(None, command_args))


class CommandOption(object):
    """
    A single command option and value validator.
    """
    def __init__(self, option_element):
        self.id = option_element.get("id")
        self.name = option_element.find("name").text
        self.param = option_element.find("param").text
        value_element = option_element.find("value")
        self.value_type = value_element[0].tag
        default_element = value_element.find("default")
        if default_element is None:
            self.default_value = None
        else:
            self.default_value = default_element.text
        self.required = False
        self._value = None

    def get_command_option(self):
        """
        Substitutes ${value} in the command option with an assigned value
        :return: command option string
        """
        value = self.value
        if (value is None or
                (self.value_type == "boolean" and
                    value == "false" or value is False)
           ):
            return ''
        template = string.Template(self.param)
        arg = template.substitute(value=value)
        print(arg, self.id, value)
        return arg

    @property
    def value(self):
        """
        :return: Value passed to the parameter or default value if none
        """
        if self._value is None:
            return self.default_value
        else:
            return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def __repr__(self):
        if self.value is None:
            return "{name}:{type}".format(name=self.name, type=self.value_type)
        else:
            return "{name}={value}".format(name=self.name, value=self.value)


def main():
    path = os.path.join('config', "MuscleParameters.xml")
    runner = CommandRunner(path)

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input")
    args = parser.parse_args()

    if args.input is None:
        print("no input file, saving to MuscleOptions.json")
        options = runner.get_options()
        save_json(options, "MuscleOptions.json")
    else:
        values = get_values_from_json(args.input)
        runner.set_values(values)
        print(runner.build_command())


def get_values_from_json(path):
    with open(path, "r") as f:
        obj = json.load(f)
    return {id: o['value'] for (id, o) in obj.items()}


def save_json(options, path):
    obj = {
        option.id: {
            "name": option.name,
            "value": option.default_value
        }
        for option in options
    }
    with open(path, "w") as f:
        json.dump(obj, f, indent=4)


if __name__ == "__main__":
    main()
