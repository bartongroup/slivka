#!usr/bin/env
import string
import subprocess

from collections import namedtuple
from copy import deepcopy

from lxml import etree


ServiceOutput = namedtuple("ServiceOutput", ["retcode", "stdout", "stderr"])


class CommandRunnerFactory(object):

    def __init__(self, binary_file, param_file):
        xml_tree = self._validate_param_file(param_file)
        self._load_options(xml_tree)
        self.binary = binary_file

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
        :return: CommandOption instance constructed from the tree element
        """
        opt_id = element.get("id")
        name = element.find("name").text
        select = element.find("select")

        if select is None:
            # param and value pair
            param = element.find("param").text
            value_element = element[3]
            value_type = value_element.tag[:-5]
            default_element = value_element.find("default")
            if default_element is None:
                default = None
            else:
                default = default_element.text
            return CommandOption(opt_id, name, value_type, param, default)
        else:
            # select field
            return CommandOption(opt_id, name, "select")

    def get_command_runner(self):
        """
        :return: command runner instance with options and binary executable
                 bound to it
        """
        options = deepcopy(self.options)
        return CommandRunner(self.binary, options)


class CommandRunner(object):

    def __init__(self, binary, options, env=None):
        """
        :param binary: binary file to be executes
        :param options: list of command options
        :param env: environment variables
        :type env: {variable: path} dictionary
        """
        self.options = options
        self.binary = binary
        self.env = env

    def set_values(self, values):
        """
        Sets values to the option parameters
        :param values: option id and value pairs
        :type values: {id: value} dictionary
        """
        for option in self.options:
            option.value = values.get(option.id)

    def run_command(self):
        """
        Runs a command with specified set of options.
        :return: named tuple ServiceOutput with data returned by the command
        """
        cmd = "{bin} {opt}".format(
            bin=self.binary, opt=self.build_command_options()
        )
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env
        )
        process.wait()
        stdout, stderr = process.communicate()
        retcode = process.returncode
        return ServiceOutput(retcode, stdout, stderr)

    def build_command_options(self):
        """
        Builds a command line joining all command options.
        :return: full command line of parameters
        """
        command_args = [option.get_cmd_option() for option in self.options]
        return " ".join(filter(None, command_args))


class CommandOption(object):

    def __init__(self, opt_id, name, value_type, param=None, default=None):
        self.id = opt_id
        self.name = name
        self.type = value_type
        if value_type == "select":
            self.param = "${value}"
        else:
            if param is None:
                raise ValueError("param must not be None")
            self.param = param
        self.default = default
        self._value = None

    def get_cmd_option(self):
        """
        Substitutes ${value} in the command option with the assigned value
        :return: command option string
        """
        value = self.value
        if (value is None or
                (self.type == "boolean" and
                    value == "false" or value is False)):
            return ''
        template = string.Template(self.param)
        arg = template.substitute(value=value)
        return arg

    @property
    def value(self):
        """
        :return: Value passed to the parameter or default value if none
        """
        if self._value is None:
            return self.default
        else:
            return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def __repr__(self):
        """
        :return: string representation of the object
        """
        if self.value is None:
            return "{name}:{type}".format(name=self.name, type=self.type)
        else:
            return "{name}={value}".format(name=self.name, value=self.value)
