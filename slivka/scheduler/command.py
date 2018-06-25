import os
import re
import shlex
import string


class CommandOption:
    """
    This class provides a building block for command line construction.
    Each ``CommandOption`` instance corresponds to a single option or
    argument which can be passed to the command.
    ``CommandOption`` holds a template of the argument with *$value* in place
    of the option value. Using ``get_cmd_option`` you can insert a
    specific value to the template and obtain the command arguments.

    >>> opt = CommandOption('optName', '-o $value', default='default')
    >>> opt.get_cmd_option()
    '-o default'
    >>> opt.get_cmd_option('hello')
    '-o hello'

    >>> opt = CommandOption('optName', 'arg')
    >>> opt.get_cmd_option()  # None
    >>> opt.get_cmd_option(True)
    'arg'
    """

    def __init__(self, name, param, default=None):
        """
        :param name: option name referring to the form field
        :param param: command parameter template
        :param default: default value
        """
        self._name = name
        self._param_template = string.Template(param)
        self._default = default

    def get_cmd_option(self, value=None):
        """Return command option with inserted value.

        Inserts specified value to option template. If ``value`` is not
        given then use default value. If the value still evaluates to
        ``None``, return ``None`` so the option will be skipped in further
        processing.

        :param value: value of the field
        :return: command option string
        :rtype: str
        """
        if value is None:
            value = self._default
        if value is None:
            return None
        else:
            return self._param_template.substitute(
                value=shlex.quote(str(value))
            )

    @property
    def name(self):
        return self._name

    def __repr__(self):
        return "<Option {0}>".format(self.name)


class PathWrapper:
    """
    This class provides a uniform way to obtain path(s) to output files
    produced by the running job. Path to the file is appended to the current
    working directory of the job.
    """

    def __init__(self, path):
        self._path = path

    def get_paths(self, cwd):
        """Get the full absolute path to the output file.

        Returns an absolute path to the output file regardless of its
        existence on the file system.

        :return: list with a single path to the file
        :rtype: list[str]
        """
        path = os.path.abspath(os.path.join(cwd, self._path))
        return [path]

    def __repr__(self):
        return self._path


class PatternPathWrapper(PathWrapper):
    """
    Extends the simple ``PathWrapper`` providing the ability to return
    multiple paths to all files matched by the regular expression.
    """

    def __init__(self, path):
        """
        :param path: regex pattern
        """
        super().__init__(path)
        self._regex = re.compile(self._path)

    def get_paths(self, cwd):
        """Get paths to files matched by the pattern.

        Returns the list of paths to all files in the current working
        directory of the job matching the regular expression that exist at
        the moment of the function call.
        Can return an empty list if there are no files matching the regex.

        :return: list of paths matching the regex
        :rtype: list[str]
        """
        files = os.listdir(cwd)
        return [
            os.path.abspath(os.path.join(cwd, name))
            for name in files
            if self._regex.match(name)
        ]
