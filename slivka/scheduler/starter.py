import contextlib
import copy
import filecmp
import itertools
import logging
import os
import shlex
import shutil
from collections import namedtuple, ChainMap
from typing import Optional, Union, List, Dict, Tuple, Sequence, Iterable

from slivka import JobStatus
from slivka.conf import ServiceConfig
from slivka.utils import expandvars
from .runner import Job, Command, BaseCommandRunner

log = logging.getLogger('slivka.scheduler')


RunnerID = namedtuple('RunnerID', 'service, runner')


class CommandStarter:
    _next_id = (RunnerID('unknown', 'runner-%d' % i)
                for i in itertools.count(1)).__next__

    def __init__(self,
                 runner_id: Optional[RunnerID],
                 base_command: Union[str, List[str]],
                 args: List[ServiceConfig.Argument],
                 env: Dict[str, str]):
        self.id: RunnerID = runner_id or self._next_id()

        self.env = {
            "PATH": os.getenv("PATH"),
            "SLIVKA_HOME": os.getenv("SLIVKA_HOME", os.getcwd())
        }
        self.env.update(env)
        for key, val in self.env.items():
            self.env[key] = expandvars(val, os.environ)

        if isinstance(base_command, str):
            base_command = shlex.split(base_command)
        # interpolate any variables in the command and arguments
        environ = ChainMap(self.env, os.environ)
        self.base_command = [
            expandvars(arg, environ) for arg in base_command
        ]
        # make copies so `arg` can be changed safely
        self.arguments = list(map(copy.copy, args))
        for argument in self.arguments:
            args = expandvars(argument.arg, environ)
            argument.arg = shlex.split(args)

        self.runner: Optional[BaseCommandRunner] = None

    name = property(lambda self: self.id.runner)
    service_name = property(lambda self: self.id.service)

    @staticmethod
    def _symlink_name(name, count):
        return '%s.%04d' % (name, count)

    def build_command_args(self, values) -> List[str]:
        """ Inserts given values and returns a list of arguments.

        Prepares the command line arguments using values from
        the config file then substituting environment variables
        and inserting values for $(value) placeholder.

        :param values: values to inserted to the command arguments
        :type values: dict[str, Any]
        :return: list of command line arguments
        """
        args = self.base_command.copy()
        for argument in self.arguments:
            value = values.get(argument.id)
            if value is None:
                value = argument.default
            if value is None or value is False:
                continue

            if isinstance(value, list):
                if argument.symlink:
                    value = [self._symlink_name(argument.symlink, i)
                             for i in range(len(value))]
                if argument.join is not None:
                    value = str.join(argument.join, value)
            elif argument.symlink:
                value = argument.symlink

            if isinstance(value, list):
                args.extend(
                    arg.replace('$(value)', val)
                    for val in value
                    for arg in argument.arg
                )
            else:
                args.extend(
                    arg.replace('$(value)', value)
                    for arg in argument.arg
                )
        return args

    def _prepare_job(self, inputs, cwd):
        with contextlib.suppress(FileExistsError):
            os.mkdir(cwd)
        for argument in self.arguments:
            if argument.symlink:
                val = inputs.get(argument.id)
                if isinstance(val, list):
                    for i, src in enumerate(val):
                        if not os.path.isfile(src):
                            raise FileNotFoundError("file '%s' does not exist")
                        dst = self._symlink_name(argument.symlink, i)
                        _mklink(src, os.path.join(cwd, dst))
                elif isinstance(val, str):
                    if not os.path.isfile(val):
                        raise FileNotFoundError("file '%s' does not exist")
                    _mklink(val, os.path.join(cwd, argument.symlink))
                # None is also an option here and should be ignored

    def start(self, requests: Iterable[Tuple[dict, str]]) -> Sequence[Job]:
        """ Runs commands with the executor.

        Prepares the command for execution by creating working
        directories and necessary symlinks. Then, constructs command
        line arguments and sends all the data to the executor
        for submission.

        :param requests: list of pairs of input parameters and
            working directories for the new jobs
        :return: sequence of newly created jobs
        """
        commands = []
        for inp, cwd in requests:
            self._prepare_job(inp, cwd)
            args = self.build_command_args(inp)
            commands.append(Command(args, cwd, self.env))
        for i, cmd in zip(itertools.count(1), commands):
            log.info(
                "Runner(%s, %s) is starting command \"%s\" in %s (%d of %d)",
                *self.id, ' '.join(map(repr, cmd.args)), cmd.cwd, i, len(commands)
            )
        try:
            return self.runner.start(commands)
        except AttributeError as e:
            if self.runner is None:
                raise Exception("Illegal state. Executor not set.") from e
            else:
                raise

    def status(self, jobs: List[Job]) -> List[JobStatus]:
        """ Checks the status of the jobs.

        Delegates the status check to the associated
        :py:class:`BaseCommandRunner` and returns it's result.
        The statuses are returned in the same order as job provided.
        """
        try:
            return self.runner.status(jobs)
        except AttributeError as e:
            if self.runner is None:
                raise Exception("Illegal state. Executor not set.") from e
            else:
                raise

    def cancel(self, jobs: List[Job]):
        """ Cancels the jobs.

        Delegates jobs cancellation to the associated
        :py:class:`BaseCommandRunner`.
        """
        try:
            self.runner.cancel(jobs)
        except AttributeError as e:
            if self.runner is None:
                raise Exception("Illegal state. Executor not set.") from e
            else:
                raise


def _mklink(src, dst):
    try:
        os.symlink(src, dst)
    except FileExistsError as e:
        if not filecmp.cmp(src, dst):
            raise e
    except OSError:
        try:
            os.link(src, dst)
        except FileExistsError as e:
            if not filecmp.cmp(src, dst):
                raise e
        except OSError:
            with contextlib.suppress(shutil.SameFileError):
                shutil.copyfile(src, dst)
