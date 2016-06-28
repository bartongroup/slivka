import os
import subprocess


class LocalCommand:
    """
    Class used for local command execution. It's subclassed by the
    CommandFactory
    """

    _env = None
    _binary = None
    _options = None

    def __init__(self, options, cwd=None):
        """
        :param options: values passed to the command runner
        :type options: dictionary of option name value pairs
        :param cwd: working directory of the application
        """
        self._values = options
        self._cwd = os.path.abspath(cwd)
        try:
            os.makedirs(self._cwd)
        except FileExistsError:
            pass
        self._process = None

    def run(self):
        return self.run_command()

    def run_command(self):
        """
        Executed the command locally as a new subprocess.
        :return: ServiceOutput tuple
        """
        stdout = stderr = ""
        try:
            self._process = subprocess.Popen(
                self.get_full_cmd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.env,
                cwd=self._cwd
            )
            stdout, stderr = self._process.communicate()
        finally:
            return_code = self._process and self._process.returncode
            return return_code, stdout.decode(), stderr.decode()

    def get_full_cmd(self):
        return "{bin} {opt}".format(
            bin=self.binary, opt=self.build_command_options()
        )

    def build_command_options(self):
        """
        Joins all option command segments into one string.
        :return: command options string
        """
        return " ".join(
            filter(
                None,
                (option.get_cmd_option(self._values.get(option.name))
                 for option in self.options)
            )
        )

    @property
    def options(self):
        if self._options is None:
            raise AttributeError("options are not set")
        return self._options

    @property
    def env(self):
        return dict(os.environ, **(self._env or {}))

    @property
    def binary(self):
        if self._binary is None:
            raise AttributeError("binary file path is not set")
        return self._binary

    def __repr__(self):
        return "<{0}>".format(self.__class__.__name__)
