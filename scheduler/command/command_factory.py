import configparser
import os
import string
import subprocess
from collections import namedtuple

import yaml

import settings
from scheduler.task_queue import RunnableTask


class BaseCommand:

    _options = None
    _binary = None
    _env = None

    def __init__(self, values):
        """
        :param values: values passed to the command runner
        :type values: dictionary of option name value pairs
        """
        self.values = values

    def run_command(self):
        raise NotImplementedError

    def build_command_options(self):
        """
        Joins all option command segments into one string.
        :return: command options string
        """
        return " ".join(
            filter(
                None,
                (option.get_cmd_option(self.values.get(option.name))
                 for option in self.options)
            )
        )

    @property
    def options(self):
        if self._options is None:
            raise AttributeError("options are not set")
        return self._options

    @property
    def binary(self):
        if self._binary is None:
            raise AttributeError("binary file path is not set")
        return self._binary

    @property
    def env(self):
        return dict(os.environ, **(self._env or {}))

    def __reduce__(self):
        """
        Tells the pickler how to recreate the object after deserialize.
        :return: tuple containing callable and its arguments
        """
        reduced = (
            CommandFactory.recreate_command,
            (
                self.__class__.__name__,
                self.__class__.__bases__,
                self._binary,
                self._options,
                self._env,
                self.values
            )
        )
        return reduced

    def __repr__(self):
        return "<{0}>".format(self.__class__.__name__)


class LocalCommand(BaseCommand, RunnableTask):
    """
    Class used for local command execution. It extends BaseCommand class to
    be able to process command options and RunnableTask to be send to local
    task queue.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._process = None

    def run(self, *args, **kwargs):
        return self.run_command()

    def suspend(self):
        pass

    def resume(self):
        pass

    def kill(self):
        pass

    def run_command(self):
        """
        Executed the command locally as a new subprocess.
        :return: ServiceOutput tuple
        """
        self._process = subprocess.Popen(
            self.get_full_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env
        )
        self._process.wait()
        stdout, stderr = map(bytes.decode, self._process.communicate())
        retcode = self._process.returncode
        return ServiceOutput(retcode, stdout, stderr)

    def get_full_cmd(self):
        return "{bin} {opt}".format(
            bin=self.binary, opt=self.build_command_options()
        )


class CommandOption:

    def __init__(self, name, val_type, param=None, default=None):
        """
        :param name: name of the option
        :param val_type: value type
        :param param: parameter template
        :param default: default value
        """
        self.name = name
        self.type = val_type
        if val_type == "select":
            param = param or "${value}"
        elif param is None:
            raise TypeError("__init__() missing required argument: \"param\"")
        self.param_template = string.Template(param)
        self.default = default

    def get_cmd_option(self, value=None):
        """
        Injects specified value to command option value. If `value` is not
        given then use default value.
        :param value: value of the field
        :return: command option and value string
        """
        if value is None:
            value = self.default
        if (value is None or
                (self.type == "boolean" and
                    (not bool(value) or value in ["false", "False", "0"]))):
            return ""
        return self.param_template.substitute(value=value)

    def __repr__(self):
        return "<Option {0}: {1}>".format(self.name, self.type)


ServiceOutput = namedtuple("ServiceOutput", ["retcode", "stdout", "stderr"])


class CommandFactory:

    @staticmethod
    def get_local_command_class(service):
        """
        Constructs a local command class from the config file data.
        Values are taken from the section corresponding to the service name.
        :param service: name of the service
        :return: command class subclassing LocalCommand
        """
        parser = configparser.ConfigParser()
        with open(settings.SERVICE_CONFIG) as f:
            parser.read_file(f)
        binary = parser.get(service, "bin")
        command_file = parser.get(service, "command_file")
        with open(command_file) as f:
            data = yaml.load(f)
        options = CommandFactory._parse_options(data['options'])
        env = {
            key[4:]: value
            for key, value in parser.items(service)
            if key.startswith("env.")
        } or None
        return CommandFactory.get_command_class(
            service=service,
            binary=binary,
            options=options,
            env=env,
            base=LocalCommand
        )

    @staticmethod
    def recreate_command(cls_name, base_classes, binary, options, env, values):
        """
        Method used by BaseCommand.__reduce__ to re-built the object after
        pickling.
        :param cls_name: command class name
        :param base_classes: bases of the command class
        :param binary: binary file path
        :param options: list of options of the command
        :param env: dictionary od environment variables
        :param values: values put to the command constructor
        :return: command object
        """
        command_cls = type(
            cls_name, base_classes,
            {
                "_binary": binary,
                "_options": options,
                "_env": env
            }
        )
        return command_cls(values)

    @staticmethod
    def get_command_class(service, binary, options, env=None,
                          base=BaseCommand):
        """
        Constructs a new command class from the service name, and command
        execution configuration data.
        :param service: name of the service
        :param binary: path to binary which will be executed
        :param options: list of command options
        :type options: [CommandOption]
        :param env: environment variables needed for script to run
        :type env: dict
        :param base: base class for a new command object
        :type base: BaseCommand
        :return: dynamically created command class
        """
        return type(
            "{0}{1}".format(service, base.__name__),
            (base, ),
            {
                "_binary": binary,
                "_options": options,
                "_env": env
            }
        )

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
                val_type=option["type"],
                param=option["param"],
            )
            for option in options
        ]

