import logging
import os
import platform
import re
import shlex
import shutil
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from typing import Type, Optional, List, Dict, Tuple, Iterable

import slivka.utils
from slivka.scheduler.exceptions import QueueBrokenError, QueueError
from slivka.scheduler.limits import LimitsBase
from slivka.utils import JobStatus

logger = logging.getLogger('slivka.scheduler.scheduler')

CommandOption = namedtuple('CommandOption', ['name', 'param', 'default'])
RunConfiguration = namedtuple(
    'RunConfiguration',
    ['name', 'runner', 'executable', 'queue_args', 'env']
)
Link = namedtuple('Link', ['src', 'dst'])
Result = namedtuple('Result', ['type', 'mimetype', 'path', 'title'])


class RunnerFactory:

    def __init__(self, *, options, results, configurations,
                 limits: Type[LimitsBase]):
        """
        :type options: list[CommandOption]
        :type results: list[Result]
        :type configurations: dict[str, RunConfiguration]
        """
        if set(limits.configurations) != set(configurations.keys()):
            raise ValueError('configurations list in %s %s does not match '
                             'those in the command description %s'
                             % (limits.__name__, limits.configurations,
                                list(configurations)))
        self._options = options
        self._results = results
        self._configurations = configurations
        self._limits = limits

    @classmethod
    def new_from_configuration(cls, config) -> 'RunnerFactory':
        options = [
            CommandOption(option['ref'], option['param'], option.get('val'))
            for option in config.get('options', [])
        ]
        results = [
            Result(r['type'], r.get('mimetype'), r['path'], None)
            for r in config.get('results', [])
        ]
        configurations = {}
        for name, configuration in config.get('configurations', {}).items():
            runner_cp = configuration['runner']
            if '.' not in runner_cp:
                runner_cp = 'slivka.scheduler.runners.' + runner_cp
            runner_class = slivka.utils.locate(runner_cp)
            executable = (configuration['executable']
                          .replace('${project_dir}', slivka.settings.BASE_DIR))
            if platform.system() == 'Windows':
                executable = executable.replace('\\', '\\\\')
            queue_args = configuration.get('queueArgs')
            if isinstance(queue_args, str):
                queue_args = shlex.split(queue_args)
            configurations[name] = RunConfiguration(
                name=name,
                runner=runner_class,
                executable=executable,
                queue_args=queue_args,
                env=configuration.get('env')
            )
        limits = slivka.utils.locate(config['limits'])
        if not issubclass(limits, LimitsBase):
            raise TypeError('%s is not of LimitsBase type' % config['limits'])
        return cls(options=options, results=results,
                   configurations=configurations, limits=limits)

    @property
    def options(self):
        return self._options

    @property
    def results(self):
        return self._results

    @property
    def configurations(self):
        return self._configurations

    def get_runner_class(self, name) -> Type['Runner']:
        return self.configurations[name].runner

    @property
    def limits(self):
        return self._limits

    def new_runner(self, values, cwd) -> Optional['Runner']:
        name = self._limits().select_configuration(values)
        if name is None:
            return None
        conf = self._configurations[name]
        return conf.runner(
            factory=self,
            configuration=conf,
            values=values,
            cwd=cwd
        )


class Runner(metaclass=ABCMeta):
    pattern = re.compile(
        r'\${(?:(?P<value>value)|(?:file:(?P<file>.+?))|(?P<env>\w+?))}'
    )

    def __init__(self, factory, configuration, values, cwd):
        """
        :type factory: RunnerFactory
        :type configuration: RunConfiguration
        :type values: dict[str, str]
        """
        assert isinstance(self, configuration.runner)
        self._factory = factory
        self._configuration = configuration
        self._values = values
        self._cwd = os.path.normpath(cwd)
        env = (configuration.env or {}).copy()
        def replace(m): return os.environ.get(m.group(1))
        for key, val in env.items():
            env[key] = re.sub(r'\${(\w+?)}', replace, val)
        self._env = os.environ.copy()
        self._env.update(env)
        self._links = []
        self._args = self.__build_args(factory.options, values)

    def __build_args(self, options, values):
        """
        :type options: list[CommandOption]
        :type values: dict[str, str]
        """
        args = []

        def replace(match):
            if match.group('file'):
                destination = os.path.normpath(match.group('file'))
                source = os.path.normpath(value)
                if destination.startswith('..'):
                    raise ValueError(
                        'Input file points outside the working directory'
                    )
                self._links.append(Link(src=source, dst=destination))
                return shlex.quote(match.group('file'))
            if match.group('value'):
                return shlex.quote(value)
            if match.group('env'):
                try:
                    return self._env[match.group('env')]
                except KeyError:
                    return match.group(0)

        for option in options:
            value = values.get(option.name)
            if value is None:
                value = option.default
            if value is None:
                continue
            token = self.pattern.sub(replace, option.param)
            args.extend(shlex.split(token))
        return args

    def prepare(self):
        if not os.path.isdir(self._cwd):
            os.mkdir(self._cwd)
        for link in self._links:
            destination = os.path.join(self._cwd, link.dst)
            try:
                os.symlink(link.src, destination)
            except OSError:
                try:
                    os.link(link.src, destination)
                except OSError:
                    shutil.copyfile(link.src, destination)

    @property
    def configuration(self) -> RunConfiguration:
        return self._configuration

    @property
    def args(self) -> List[str]:
        return self._args

    @property
    def queue_args(self) -> List[str]:
        return self._configuration.queue_args or []

    @property
    def executable(self) -> List[str]:
        return shlex.split(self._configuration.executable)

    @property
    def cwd(self) -> str:
        return self._cwd

    @property
    def env(self) -> Dict[str, str]:
        return self._env

    def start(self) -> 'JobHandler':
        try:
            job_handler = self.submit()
            job_handler.cwd = self.cwd
            job_handler.runner = self.__class__
        except QueueError:
            raise
        except Exception as e:
            logger.critical("Critical error occurred when submitting the job",
                            exc_info=True)
            raise QueueBrokenError from e
        return job_handler

    @abstractmethod
    def submit(self) -> 'JobHandler':
        pass

    @classmethod
    @abstractmethod
    def get_job_handler_class(cls) -> Type['JobHandler']:
        pass

    @staticmethod
    def get_job_status(job_handlers: List['JobHandler']) \
            -> Iterable[Tuple['JobHandler', JobStatus]]:
        return [
            (handler, handler.get_status())
            for handler in job_handlers
        ]


class JobHandler(metaclass=ABCMeta):

    def __init__(self, cwd=None, runner_class=None):
        self._runner_class = runner_class
        self._cwd = cwd

    @property
    @abstractmethod
    def id(self) -> str:
        pass

    @property
    def cwd(self):
        return self._cwd

    @cwd.setter
    def cwd(self, value):
        self._cwd = value

    @property
    def runner_class(self):
        return self._runner_class

    @runner_class.setter
    def runner_class(self, value):
        self._runner_class = value

    @abstractmethod
    def get_status(self) -> JobStatus:
        pass

    def is_finished(self):
        return self.get_status() not in {
            JobStatus.PENDING,
            JobStatus.STATUS_QUEUED,
            JobStatus.STATUS_RUNNING
        }

    @abstractmethod
    def serialize(self) -> str:
        pass

    @classmethod
    @abstractmethod
    def deserialize(cls, serial) -> 'JobHandler':
        pass
