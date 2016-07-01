import configparser
import os.path
import re
import string
import uuid

import jsonschema
import yaml

import pybioas
import pybioas.utils
from pybioas.scheduler.command.local_command import LocalCommand


class CommandOption:

    def __init__(self, name, param, default=None):
        """
        :param name: name of the option
        :param param: parameter template
        :param default: default value
        """
        self._name = name
        self._param_template = string.Template(param)
        self._default = default

    def get_cmd_option(self, value=None):
        """
        Injects specified value to command option value. If `value` is not
        given then use default value.
        :param value: value of the field
        :return: command option as string
        """
        if value is None:
            value = self._default
        if value is None:
            return ""
        elif value is False:
            return self._param_template.substitute(value="")
        return self._param_template.substitute(value=value)

    @property
    def name(self):
        return self._name

    def __repr__(self):
        return "<Option {0}>".format(self._name)


class FileOutput:

    def __init__(self, name):
        self._name = name

    def get_files_paths(self, cwd):
        return [os.path.abspath(os.path.join(cwd, self._name))]


class PatternFileOutput(FileOutput):

    def __init__(self, pattern):
        super().__init__(None)
        self._regex = re.compile(pattern)

    def get_files_paths(self, cwd):
        files = os.listdir(cwd)
        return [
            os.path.abspath(os.path.join(cwd, name))
            for name in files
            if self._regex.match(name)
        ]


class CommandFactory:

    _commands = {}

    @classmethod
    def get_local_command_class(cls, service):
        """
        Constructs a local command class from the config file data.
        Values are taken from the section corresponding to the service name.
        :param service: name of the service
        :return: command class subclassing LocalCommand
        """
        try:
            command_cls = cls._commands[service]
        except KeyError:
            parser = configparser.ConfigParser()
            with open(pybioas.settings.SERVICE_CONFIG) as f:
                parser.read_file(f)
            command_file = parser.get(service, "command_file")
            with open(command_file) as f:
                data = yaml.load(f)
            jsonschema.validate(data, pybioas.utils.COMMAND_SCHEMA)
            binary = parser.get(service, "bin")
            options = CommandFactory._parse_options(data['options'])
            outputs = CommandFactory._parse_outputs(data['outputs'], options)
            env = {
                key[4:]: value
                for key, value in parser.items(service)
                if key.startswith("env.")
            } or None
            command_cls = type(
                "{0}{1}".format(service, "LocalCommand"),
                (LocalCommand, ),
                {
                    "_binary": binary,
                    "_options": options,
                    "_output_files": outputs,
                    "_env": env
                }
            )
            cls._commands[service] = command_cls
        return command_cls

    @staticmethod
    def _parse_options(options):
        """
        Parses options dictionary into command option objects
        :param options: list of option descriptions
        :type options: [dict(name=string, type=string, param=string)]
        :return: list of command option objects
        :rtype: [CommandOption]
        """
        return [
            CommandOption(
                name=option["name"],
                param=option["parameter"],
                default=option["value"].get("default")
            )
            for option in options
        ]

    @staticmethod
    def _parse_outputs(outputs, options):
        """

        :param outputs:
        :param options:
        :return:
        :raise KeyError:
        """
        res = []
        for out in outputs:
            if out["method"] == "file":
                if "filename" in out:
                    res.append(FileOutput(out["filename"]))
                elif "parameter" in out:
                    filename = uuid.uuid4().hex + ".pybioas"
                    res.append(FileOutput(filename))
                    options.append(
                        CommandOption("", out["parameter"], filename)
                    )
                elif "pattern" in out:
                    res.append(PatternFileOutput(out["pattern"]))
                else:
                    raise KeyError("None of the keys 'filename', "
                                   "'parameter', 'pattern' found.")
        return res
