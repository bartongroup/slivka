import configparser
import os.path
import re
import shlex
import string
import uuid

import jsonschema
import yaml

import pybioas
import pybioas.utils
from pybioas.scheduler.command.local_command import LocalCommand


class CommandOption:

    def __init__(self, name, param, type='text', default=None):
        """
        :param name: name of the option
        :param param: parameter template
        :param default: default value
        """
        self._name = name
        self._param_template = string.Template(param)
        self._type = type
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
        elif self._type == "boolean" and (not value or value == "0"):
            return self._param_template.substitute(value="")
        return self._param_template.substitute(value=shlex.quote(str(value)))

    @property
    def name(self):
        return self._name

    def __repr__(self):
        return "<Option {0}>".format(self.name)


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

    # review: may be better to pass ConfigParser object
    def __init__(self, config_file):
        """
        Loads all command configurations from the config file.
        :param config_file: path to service.ini config file
        :raise FileNotFoundError: config file is missing
        :raise configparser.NoOptionError
        :raise yaml.YAMLError
        :raise jsonschema.exceptions.ValidationError
        """
        parser = configparser.ConfigParser()
        with open(config_file) as file:
            parser.read_file(file)
        self._configurations = dict()
        for configuration in parser.sections():
            with open(parser.get(configuration, 'command_file')) as file:
                data = yaml.load(file)
            jsonschema.validate(data, pybioas.utils.COMMAND_SCHEMA)
            binary = parser.get(configuration, 'bin')
            options = self._parse_options(data['options'])
            outputs, extra_options = self._parse_outputs(data['outputs'])
            options.extend(extra_options)
            env = {
                key[4:]: value
                for key, value in parser.items(configuration)
                if key.startswith('env.')
            } or None
            command_cls = type(
                '{0}{1}'.format(configuration, 'LocalCommand'),
                (LocalCommand,),
                {
                    '_binary': binary, '_options': options,
                    '_output_files': outputs, '_env': env
                }
            )
            self._configurations[configuration] = command_cls

    @staticmethod
    def _parse_options(options):
        """
        Parses options dictionary into command option objects
        :param options: list of option descriptions
        :type options: list[dict]
        :return: list of command option objects
        :rtype: list[CommandOption]
        """
        return [
            CommandOption(
                name=option["name"],
                param=option["parameter"],
                type=option["value"].get("type"),
                default=option["value"].get("default")
            )
            for option in options
        ]

    @staticmethod
    def _parse_outputs(outputs):
        """
        :param outputs:
        :return: tuple of outputs list and extra options list
        :rtype (list[FileOutput], list[CommandOption])
        :raise KeyError: file output element is missing attribute
        """
        res = []
        options = []
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
        return res, options

    def get_command_class(self, configuration):
        """
        Returns a local command class built from the config file data.
        Configuration name is a corresponding section in the config file.
        :param configuration: name of the configuration
        :return: command class subclassing LocalCommand
        :rtype: type[LocalCommand]
        :raise KeyError: specified configuration does not exist
        """
        return self._configurations[configuration]

    @property
    def configurations(self):
        """
        :return: configurations and commands dictionary
        :rtype: dict[str, type[LocalCommand]]
        """
        return self._configurations
