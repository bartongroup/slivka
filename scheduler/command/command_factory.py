import configparser
import string

import jsonschema
import yaml

import settings
import utils
from scheduler.command.local_command import LocalCommand


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
        if value is None or value is False:
            return self._param_template.substitute(value="")
        return self._param_template.substitute(value=value)

    @property
    def name(self):
        return self._name

    def __repr__(self):
        return "<Option {0}>".format(self._name)


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
            with open(settings.SERVICE_CONFIG) as f:
                parser.read_file(f)
            command_file = parser.get(service, "command_file")
            with open(command_file) as f:
                data = yaml.load(f)
            jsonschema.validate(data, utils.COMMAND_SCHEMA)
            binary = parser.get(service, "bin")
            options = CommandFactory._parse_options(data['options'])
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
