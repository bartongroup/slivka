import contextlib
import filecmp
import itertools
import logging
import os
import re
import shlex
import shutil
import tempfile
import time
from collections import ChainMap, namedtuple
from datetime import datetime
from functools import partial
from typing import List, Iterable, Tuple, Match, Any

import slivka
from slivka import JobStatus
from slivka.db.documents import JobMetadata

log = logging.getLogger('slivka.scheduler')


# Regular expression capturing variable names $VAR or ${VAR}
# and escaped dollar sign $$. Matches should be substituted
# using _replace_from_env function.
_envvar_regex = re.compile(
    r'\$(?:(\$)|([_a-z]\w*)|{([_a-z]\w*)})',
    re.UNICODE | re.IGNORECASE
)


def _replace_from_env(env: dict, match: Match):
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


RunInfo = namedtuple('RunInfo', 'id, cwd')
RunnerID = namedtuple('RunnerID', 'service_name, runner_name')


class Runner:
    """ An abstract class responsible for job execution and management.

    This is an abstract base class which all runners should extends
    serving as an abstraction layer between the scheduler and
    external scheduling/queuing systems.
    It provides methods for constructing command line arguments,
    and retrieving environment variables configured for the service.

    Concrete implementations must define ``submit``, ``check_status``
    and ``cancel`` methods which submit the command to the queuing
    system, check the current status of the job and can cancel
    running job respectively.

    All runners are instantiated from the data provided in the
    configuration *service.yaml* files on scheduler startup and
    stored and used by it.

    All subclasses' constructors must have at least two parameters
    ``command_def`` and ``id`` which are passed directly to their
    superclass' (this class) constructor.

    :param command_def: command definition loaded from the config
        file defined by *slivka/conf/commandDefSchema.json*
    :type command_def: dict
    :param id: identifier containing service and runner name,
        defaults to None
    :type id: RunnerID
    :param jobs_dir: path to the directory the jobs will be run under,
        None sets it to the ``JOBS_DIR`` from the workspace settings,
        defaults to None
    """
    _next_id = (RunnerID('unknown', 'runner-%d' % i)
                for i in itertools.count(1)).__next__
    JOBS_DIR = None

    def __init__(self, command_def, id=None, jobs_dir=None):
        self.jobs_dir = jobs_dir or self.JOBS_DIR or slivka.settings.jobs_dir
        self.id = id or self._next_id()
        self.inputs = command_def['inputs']
        self.outputs = command_def['outputs']  # TODO: redundant field
        self.env = env = {
            'PATH': os.getenv('PATH'),
            'SLIVKA_HOME': os.getenv('SLIVKA_HOME', os.getcwd())
        }
        env.update(command_def.get('env', {}))
        replace = partial(_replace_from_env, os.environ)
        # substitute variables with the system env vars
        for key, val in env.items():
            # noinspection PyTypeChecker
            env[key] = _envvar_regex.sub(replace, val)
        replace = partial(_replace_from_env, ChainMap(env, os.environ))
        base_command = command_def['baseCommand']  # type: List[str]
        if isinstance(base_command, str):
            base_command = shlex.split(base_command)
        # noinspection PyTypeChecker
        self.base_command = [
            _envvar_regex.sub(replace, arg)
            for arg in base_command
        ]
        arguments = command_def.get('arguments', [])
        # noinspection PyTypeChecker
        self.arguments = [
            _envvar_regex.sub(replace, arg)
            for arg in arguments
        ]
        self.test = command_def.get('test')

    def get_name(self): return self.id.runner_name
    name = property(get_name)

    def get_service_name(self): return self.id.service_name
    service_name = property(get_service_name)

    def get_args(self, values) -> List[str]:
        """ Inserts given values and returns a list of arguments.

        Prepares the command line arguments using values from
        the config file then substituting environment variables
        and inserting values for $(value) placeholder.

        :param values: values to inserted to the command arguments
        :type values: dict[str, Any]
        :return: list of command line arguments
        """
        replace = partial(_replace_from_env, self.env)
        args = []
        for name, inp in self.inputs.items():
            value = values.get(name)
            if value is None:
                value = inp.get('value')
            if value is None or value is False:
                continue
            # noinspection PyTypeChecker
            # fixme: no need to regex sub every time, move to __init__
            tpl = _envvar_regex.sub(replace, inp['arg'])
            param_type = inp.get('type', 'string')
            if param_type == 'flag':
                value = 'true' if value else ''
            elif param_type == 'number':
                value = str(value)
            elif param_type == 'file':
                value = inp.get('symlink', value)
            elif param_type == 'array':
                join = inp.get('join')
                if join is not None:
                    value = str.join(join, value)

            if isinstance(value, list):
                args.extend(
                    arg.replace('$(value)', val)
                    for val in value
                    for arg in shlex.split(tpl)
                )
            else:
                args.extend(
                    arg.replace('$(value)', value)
                    for arg in shlex.split(tpl)
                )
        args.extend(self.arguments)
        return args

    def run(self, inputs: dict, cwd: str = None) -> RunInfo:
        """ Runs the command in the queuing system.

        Prepares the command for execution by creating a working
        directory and linking all necessary input files.
        Then, submits the command to the queuing system with
        :py:meth:`.submit`.

        :param inputs: inputs values for the command
        :param cwd: current working directory, a new directory will
            be created if None, defaults to None
        :return: tuple containing job id and working directory
        """
        cwd = cwd or tempfile.mkdtemp(
            prefix=datetime.now().strftime("%y%m%d"), dir=self.jobs_dir
        )
        for name, input_conf in self.inputs.items():
            if input_conf.get('type') == 'file' and 'symlink' in input_conf:
                src = inputs.get(name)
                if src is not None:
                    mklink(src, os.path.join(cwd, input_conf['symlink']))
        cmd = self.base_command + self.get_args(inputs)
        log.info('%s submitting command: %s, wd: %s',
                 self.__class__.__name__, ' '.join(map(repr, cmd)), cwd)
        try:
            return RunInfo(id=self.submit(cmd, cwd), cwd=cwd)
        except Exception:
            with contextlib.suppress(OSError):
                shutil.rmtree(cwd)
            raise

    def batch_run(self, inputs_list: List[dict]) -> Iterable[RunInfo]:
        """ Runs multiple commands in the queuing system.

        An alternative to the :py:meth:`.run` method submitting
        multiple jobs at once with :py:meth:`.batch_submit`.

        :param inputs_list: list of dictionaries containing input values
        :return: iterable of job id and working directory pairs
        """
        cwds = [
            tempfile.mkdtemp(
                prefix=datetime.now().strftime("%y%m%d"), dir=self.jobs_dir
            )
            for _ in inputs_list
        ]
        cmds = []
        for cwd, inputs in zip(cwds, inputs_list):
            for name, input_conf in self.inputs.items():
                if input_conf.get('type') == 'file' and 'symlink' in input_conf:
                    src = inputs.get(name)
                    if src is not None:
                        mklink(src, os.path.join(cwd, input_conf['symlink']))
            cmd = self.base_command + self.get_args(inputs)
            cmds.append(cmd)
        if log.isEnabledFor(logging.INFO):
            for i, cmd, cwd in zip(itertools.count(1), cmds, cwds):
                log.info('%s submitting command: %s, wd: %s (%d of %d)',
                         self.__class__.__name__, ' '.join(map(repr, cmd)),
                         cwd, i, len(cmds))
        try:
            job_ids = self.batch_submit(zip(cmds, cwds))
            return map(RunInfo._make, zip(job_ids, cwds))
        except Exception:
            for cwd in cwds:
                with contextlib.suppress(OSError):
                    shutil.rmtree(cwd)
            raise

    def submit(self, cmd: List[str], cwd: str) -> Any:
        """ Submits the job to the queuing system.

        Used internally by the :py:meth:`run` method to send the jobs
        to the queuing system. Should not be called directly.

        Deriving classes must provide a concrete implementation of
        this method which sends the job to the queueing system.
        Returned job id must be json serializable and will be
        further used to monitor job status.

        :param cmd: list of command line arguments
        :param cwd: current working directory for the job
        :return: json-serializable job id
        :raise Exception: submission to the queue failed
        """
        raise NotImplementedError

    def batch_submit(self, commands: Iterable[Tuple[List[str], str]]) \
            -> Iterable[Any]:
        """ Submits multiple jobs to the queueing system.

        A variant of the :py:meth:`submit` method optimized for
        sending jobs in batches. Used internally by :py:meth:`batch_run`
        and should not be called directly. It should be implemented in
        cases where sending jobs individually has a large overhead
        (i.e. slow connection opening) and can be sped up by
        sending them in batches.

        Default implementation makes multiple calls to :py:meth:`submit`.

        :param commands: iterable of command arguments and working directory pairs
        :return: iterable of json-serializable job ids
        :raise Exception: submission to the queue failed
        """
        return [self.submit(cmd, cwd) for cmd, cwd in commands]

    @classmethod
    def check_status(cls, job_id, cwd) -> JobStatus:
        """ Returns the job status in the queuing system.

        Deriving classes must provide a concrete implementation
        which fetches the job status from the queuing system.

        :param job_id: job id as returned by :py:meth:`submit`
        :param cwd: working directory of the job
        :return: job status
        """
        raise NotImplementedError

    @classmethod
    def batch_check_status(cls, jobs: Iterable[JobMetadata]) \
            -> Iterable[JobStatus]:
        """ Returns the status of multiple jobs.

        Deriving classes may implement this method if fetching
        job status individually is too slow and cen be done
        in batches.

        Default implementation calls :py:meth:`check_status`.

        :param jobs: iterable of :py:class:`JobMetadata` objects
        """
        return [cls.check_status(job.job_id, job.work_dir) for job in jobs]

    @classmethod
    def cancel(cls, job_id, cwd):
        """ Requests the queuing system to cancel the job.

        Deriving classes must provide concrete implementation
        of this method for their queuing system.

        :param job_id: job id as returned by :py:meth:`submit`
        :param cwd: job's working directory
        """
        raise NotImplementedError

    @classmethod
    def batch_cancel(cls, jobs: Iterable[JobMetadata]):
        """ Requests cancellation of multiple jobs."""
        for job in jobs:
            cls.cancel(job['job_id'], job['work_dir'])

    def run_test(self) -> bool:
        """ Performs the test of the runner with a sample job.

        Tests are provided in the service configuration file
        and consists of input parameters and expected output files.

        :return: whether the test was successful or True if there
            is no test for that runner.
        """
        if not self.test:
            log.info("no test found for %s", self)
            return True
        log.info("starting test for %s", self)
        env = ChainMap(os.environ, {'SLIVKA_HOME': slivka.settings.base_dir})
        replace = partial(_replace_from_env, env)
        inputs = {
            key: _envvar_regex.sub(replace, val)
            for key, val in self.test['inputs'].items()
        }
        temp_dir = tempfile.TemporaryDirectory()
        try:
            job_id, cwd = self.run(inputs, temp_dir.name)
            timeout = self.test.get('timeout', 8640000)
            end_time = time.time() + timeout
            while time.time() <= end_time:
                state = self.check_status(job_id, cwd)
                if state.is_finished():
                    break
                time.sleep(1)
            else:
                raise TimeoutError
            if state != JobStatus.COMPLETED:
                raise ValueError("job status is %s" % state.name)
            for output in self.test['output-files']:
                fp = os.path.join(cwd, output['path'])
                if not os.path.isfile(fp):
                    raise FileNotFoundError("missing output file %s" % fp)
                match_fp = output.get('match')
                if match_fp:
                    match_fp = _envvar_regex.sub(replace, match_fp)
                    if not filecmp.cmp(fp, match_fp, False):
                        raise ValueError("output file %s content mismatch" % fp)
        except Exception:
            log.exception("test of %s failed", self)
            return False
        else:
            log.info("test of %s passed", self )
            return True
        finally:
            with contextlib.suppress(FileNotFoundError):
                temp_dir.cleanup()

    def __repr__(self):
        return '%s(%s-%s)' % (self.__class__.__name__, self.service_name, self.name)


def mklink(src, dst):
    try:
        os.symlink(src, dst)
    except OSError:
        try:
            os.link(src, dst)
        except OSError:
            shutil.copyfile(src, dst)
