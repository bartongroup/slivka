import os
import re
import shlex
import string


class CommandOption:

    # noinspection PyShadowingBuiltins
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
            return None
        return self._param_template.substitute(value=shlex.quote(str(value)))

    @property
    def name(self):
        return self._name

    def __repr__(self):
        return "<Option {0}>".format(self.name)


class PathWrapper:

    def __init__(self, path):
        self._path = path

    def get_paths(self, cwd):
        path = os.path.abspath(os.path.join(cwd, self._path))
        return [path]

    def __repr__(self):
        return self._path


class PatternPathWrapper(PathWrapper):

    def __init__(self, path):
        super().__init__(path)
        self._regex = re.compile(self._path)

    def get_paths(self, cwd):
        files = os.listdir(cwd)
        return [
            os.path.abspath(os.path.join(cwd, name))
            for name in files
            if self._regex.match(name)
        ]
