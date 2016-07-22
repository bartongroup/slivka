import os
import shlex
import subprocess
import uuid
from collections import namedtuple

import pybioas


class LocalCommand:
    """
    Class used for local command execution. It's subclasses are constructed by
    the CommandFactory
    """

    _env = None
    _binary = None
    _options = None
    _output_files = None

    def __init__(self, values=None):
        """
        :param values: values passed to the command runner
        :type values: dictionary of option name value pairs
        """
        self._values = values or {}
        self._process = None

    def run(self):
        return self.run_command()

    def run_command(self):
        """
        Executes the command locally as a new subprocess.
        :return: output of the running process
        :rtype: ProcessOutput
        :raise AttributeError: fields was not filled in the subclass
        :raise FileNotFoundError: working dir from settings does not exist
        :raise OSError: error occurred when starting the process
        """
        # review: working dir passed as a function argument or auto-generated
        cwd = os.path.join(pybioas.settings.WORK_DIR, uuid.uuid4().hex)
        os.mkdir(cwd)

        self._process = subprocess.Popen(
            self.get_full_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            cwd=cwd
        )
        stdout, stderr = self._process.communicate()

        return_code = self._process.returncode
        return ProcessOutput(
            return_code=return_code,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
            files=[
                filename
                for output in self.output_files
                for filename in output.get_files_paths(cwd)
            ]
        )

    def get_full_cmd(self):
        base = shlex.split(self.binary)
        options = [
            token
            for opt in filter(
                None,
                (
                    option.get_cmd_option(self._values.get(option.name))
                    for option in self.options
                )
            )
            for token in shlex.split(opt)
        ]
        return base + options

    @property
    def options(self):
        if self._options is None:
            raise AttributeError("options are not set")
        return self._options

    @property
    def output_files(self):
        return self._output_files or []

    @property
    def env(self):
        return dict(os.environ, **(self._env or {}))

    @property
    def binary(self):
        if self._binary is None:
            raise AttributeError("binary file path is not set")
        return self._binary

    def kill(self):
        pass

    def suspend(self):
        pass

    def resume(self):
        pass

    def __repr__(self):
        return "<{0}>".format(self.__class__.__name__)


ProcessOutput = namedtuple('ProcessOutput', 'return_code stdout stderr files')
