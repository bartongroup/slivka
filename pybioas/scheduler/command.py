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
            return ""
        return self._param_template.substitute(value=shlex.quote(str(value)))

    @property
    def name(self):
        return self._name

    def __repr__(self):
        return "<Option {0}>".format(self.name)


class FileResult:

    def __init__(self, path):
        self._path = path

    def get_paths(self, cwd):
        path = os.path.abspath(os.path.join(cwd, self._path))
        return [path] if os.path.exists(path) else []

    def __repr__(self):
        return self._path


class PatternFileResult(FileResult):

    def __init__(self, pattern):
        super().__init__(None)
        self._regex = re.compile(pattern)

    def get_paths(self, cwd):
        files = os.listdir(cwd)
        return [
            os.path.abspath(os.path.join(cwd, name))
            for name in files
            if self._regex.match(name)
        ]

    def __repr__(self):
        return self._regex.pattern
