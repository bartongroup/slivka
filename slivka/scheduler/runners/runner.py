import contextlib
import copy
import itertools
import logging
import os
import re
import shlex
import shutil
from collections import ChainMap, namedtuple
from functools import partial
from typing import List, Match, Union, Dict, Collection, Sequence, Optional

from slivka import JobStatus
from slivka.conf import ServiceConfig

log = logging.getLogger('slivka.scheduler')


# Regular expression capturing variable names $VAR or ${VAR}
# and escaped dollar sign $$. Matches should be substituted
# using _replace_from_env function.
_var_regex = re.compile(
    r'\$(?:(\$)|([_a-z]\w*)|{([_a-z]\w*)})',
    re.UNICODE | re.IGNORECASE
)


def _replace_vars(env: dict, match: Match):
    """ Replaces matches of _envvar_regex with variables from env

    Given the match from the ``_envvar_regex`` returns the string
    which should be substituted for the match. Escaped dollar
    "$$" is substituted for a single dollar. captured variables
    are substituted for the values from the ``env`` dictionary
    or nothing if the value is not present.
    This function is meant to imitate bash variable interpolation.

    Usage:

        _envvar_regex.sub(partial(_replace_from_env, env), cmd)

    :param env: dictionary of variables and values to be substituted
    :param match: the match object provided by ``re.sub``
    :return:
    """
    if match.group(1):
        return '$'
    else:
        return env.get(match.group(2) or match.group(3))


RunnerID = namedtuple('RunnerID', 'service, runner')
Command = namedtuple("Command", ["args", "cwd"])
Job = namedtuple("Job", ["id", "cwd"])


class Runner:
    """ An abstract class responsible for job execution and management.

    This is an abstract base class which all runners should extend
    that serves as an abstraction layer between the scheduler and
    the external execution systems.
    It provides methods for constructing command line arguments,
    and retrieving environment variables configured for the service.

    Concrete implementations must define ``submit``, ``check_status``
    and ``cancel`` methods which interact with the execution systems
    directly. Additionally, these methods have overridable ``batch_*``
    variants which may be implemented if performing those operations
    in batches is more beneficial.

    The runners are typically instantiated from the data provided in the
    configuration *service.yaml* files on scheduler startup.

    The constructors of the subclasses must have at least the same
    positional arguments that this class have and can have any
    arbitrary keyword arguments (as long as there is no name collision).
    The keyword arguments are supplied from the service config file
    from the ``parameters`` property in the runner definition section.

    :param runner_id: a tuple of service and runner id
    :param command: a string or a list of args representing a base command
    :param args: list of argument configurations in order of appearance
        in the command line
    :param outputs: list of output file definitions, unused by the
        base ``Runner`` but some implementations may make use of it.
    """
    _next_id = (RunnerID('unknown', 'runner-%d' % i)
                for i in itertools.count(1)).__next__
    JOBS_DIR = None

    def __init__(self,
                 runner_id: Optional[RunnerID],
                 command: Union[str, List[str]],
                 args: List[ServiceConfig.Argument],
                 outputs: List[ServiceConfig.OutputFile],
                 env: Dict[str, str]):
        self.id = runner_id or self._next_id()
        self.outputs = outputs

        self.env = {
            'PATH': os.getenv('PATH'),
            'SLIVKA_HOME': os.getenv('SLIVKA_HOME', os.getcwd())
        }
        self.env.update(env)
        replace = partial(_replace_vars, os.environ)
        # substitute variables with the system env vars
        for key, val in self.env.items():
            self.env[key] = _var_regex.sub(replace, val)

        replace = partial(_replace_vars, ChainMap(env, os.environ))
        if isinstance(command, str):
            command = shlex.split(command)
        self.command = [
            _var_regex.sub(replace, arg) for arg in command
        ]
        self.arguments = list(map(copy.copy, args))
        for argument in self.arguments:
            args = _var_regex.sub(replace, argument.arg)
            args = shlex.split(args)
            argument.arg = args

    def get_name(self): return self.id.runner
    name = property(get_name)

    def get_service_name(self): return self.id.service
    service_name = property(get_service_name)

    @staticmethod
    def _symlink_name(name, count):
        return '%s.%04d' % (name, count)

    def build_args(self, values) -> List[str]:
        """ Inserts given values and returns a list of arguments.

        Prepares the command line arguments using values from
        the config file then substituting environment variables
        and inserting values for $(value) placeholder.

        :param values: values to inserted to the command arguments
        :type values: dict[str, Any]
        :return: list of command line arguments
        """
        args = []
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
                        mklink(src, os.path.join(cwd, dst))
                elif isinstance(val, str):
                    if not os.path.isfile(val):
                        raise FileNotFoundError("file '%s' does not exist")
                    mklink(val, os.path.join(cwd, argument.symlink))
                # None is also an option here and should be ignored

    def start(self, inputs: dict, cwd: str) -> Job:
        """ Runs the command in the queuing system.

        Prepares the command for execution by creating a working
        directory, linking all necessary input files and constructing
        the command line arguments. It then sends the command to the queuing
        system using :py:meth:`.submit` and returns job id.

        :param inputs: inputs values for the command
        :param cwd: working directory, a new directory will be created if not
            already present
        :return: job id as returned by :py:meth:`.submit`
        """
        self._prepare_job(inputs, cwd)
        cmd = self.command + self.build_args(inputs)
        log.info('%s starting command "%s" in %s',
                 self.__class__.__name__, ' '.join(map(repr, cmd)), cwd)
        return self.submit(Command(cmd, cwd))

    def batch_start(self, inputs: List[dict], cwds: List[str]) -> Sequence[Job]:
        """ Runs multiple commands in the queuing system.

        An alternative to the :py:meth:`.run` method submitting
        multiple jobs at once with :py:meth:`.batch_submit`.

        :param inputs: list of maps containing input values for each job
        :param cwds: list of working directories for the jobs
        :return: iterable of job id and working directory pairs
        """
        cmds = []
        for cwd, inp in zip(cwds, inputs):
            self._prepare_job(inp, cwd)
            cmd = self.command + self.build_args(inp)
            cmds.append(cmd)
        if log.isEnabledFor(logging.INFO):
            for i, cmd, cwd in zip(itertools.count(1), cmds, cwds):
                log.info('%s starting command "%s" in %s (%d of %d)',
                         self.__class__.__name__, ' '.join(map(repr, cmd)),
                         cwd, i, len(cmds))
        return self.batch_submit(list(map(Command._make, zip(cmds, cwds))))

    def submit(self, command: Command) -> Job:
        """ Submits the job to the queuing system.

        Used internally by the :py:meth:`run` method to send the jobs
        to the queuing system. Should not be called directly.

        Deriving classes must provide a concrete implementation of
        this method which sends the job to the queueing system.
        Returned job id must be json serializable and will be
        further used to monitor job status.

        :param command: tuple containing command line arguments and working
            directory
        :return: Job tuple containing json-serializable job id and the
            working directory
        :raise Exception: submission to the queue failed
        """
        raise NotImplementedError

    def batch_submit(self, commands: Sequence[Command]) -> Sequence[Job]:
        """ Submits multiple jobs to the queueing system.

        A variant of the :py:meth:`submit` method optimized for
        sending jobs in batches. Used internally by :py:meth:`batch_run`
        and should not be called directly. It should be implemented in
        cases where sending jobs individually has a large overhead
        (i.e. slow connection opening) and can be sped up by
        sending them in batches.

        Default implementation makes multiple calls to :py:meth:`submit`.

        :param commands: sequence of Command tuples consisting of
            arguments list and working directory
        :return: sequence of :py:class:`Job` tuples, each containing
            json-serializable job id and the working directory
        :raise Exception: submission to the queue failed
        """
        return list(map(self.submit, commands))

    def check_status(self, job: Job) -> JobStatus:
        """ Returns the job status in the queuing system.

        Deriving classes must provide a concrete implementation
        which fetches the job status from the queuing system.

        :param job: job as returned by :py:meth:`submit`
        :return: job status
        """
        raise NotImplementedError

    def batch_check_status(self, jobs: Sequence[Job]) -> Sequence[JobStatus]:
        """ Returns the status of multiple jobs.

        Deriving classes may implement this method if fetching
        job status individually is too slow and cen be done
        in batches.

        Default implementation calls :py:meth:`check_status`.

        :param jobs: sequence of :py:class:`Job` objects
            as returned by :py:meth:`submit`
        :return: sequence of statuses for each job
        """
        return list(map(self.check_status, jobs))

    def cancel(self, job: Job):
        """ Requests the queuing system to cancel the job.

        Deriving classes must provide concrete implementation
        of this method for their queuing system.

        :param job: job as returned by :py:meth:`submit`
        """
        raise NotImplementedError

    def batch_cancel(self, jobs: Collection[Job]):
        """ Requests cancellation of multiple jobs."""
        for job in jobs:
            self.cancel(job)

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, self.service_name, self.name)


def mklink(src, dst):
    try:
        os.symlink(src, dst)
    except OSError:
        try:
            os.link(src, dst)
        except OSError:
            shutil.copyfile(src, dst)
