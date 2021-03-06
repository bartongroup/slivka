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
from typing import List, Iterator, Iterable, Tuple, Match

import slivka
from slivka import JobStatus
from slivka.db.documents import JobMetadata

log = logging.getLogger('slivka.scheduler')
_envvar_regex = re.compile(
    r'\$(?:(\$)|([_a-z]\w*)|{([_a-z]\w*)})',
    re.UNICODE | re.IGNORECASE
)

RunInfo = namedtuple('RunInfo', 'id, cwd')
RunnerID = namedtuple('RunnerID', 'service_name, runner_name')


class Runner:
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

    def run(self, inputs, cwd=None) -> RunInfo:
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
            return RunInfo(cwd=cwd, id=self.submit(cmd, cwd))
        except Exception:
            with contextlib.suppress(OSError):
                shutil.rmtree(cwd)
            raise

    def batch_run(self, inputs_list) -> Iterable[RunInfo]:
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
                log.info('%s submitting command: %s, wd: %s (%d/%d)',
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

    def submit(self, cmd, cwd):
        """
        :param cmd: list of command line arguments
        :param cwd: current working directory for the job
        :return: json-serializable job id
        :raise SubmissionError: submission to the queue failed
        """
        raise NotImplementedError

    def batch_submit(self, commands: Iterable[Tuple[List[str], str]]) -> Iterable:
        """
        :param commands: iterable of command arguments and working directory pairs
        :return: iterable of json-serializable job ids
        :raise SubmissionError: submission to the queue failed
        """
        return [self.submit(cmd, cwd) for cmd, cwd in commands]

    @classmethod
    def check_status(cls, job_id, cwd) -> JobStatus:
        raise NotImplementedError

    @classmethod
    def batch_check_status(cls, jobs: Iterable[JobMetadata]) -> Iterator[JobStatus]:
        return [cls.check_status(job.job_id, job.work_dir) for job in jobs]

    @classmethod
    def cancel(cls, job_id, cwd):
        raise NotImplementedError

    @classmethod
    def batch_cancel(cls, jobs: Iterable[JobMetadata]):
        for job in jobs:
            cls.cancel(job['job_id'], job['work_dir'])

    def run_test(self):
        if not self.test:
            log.info("no test for runner %s", self)
            return
        log.info("running test for %s", self)
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
            log.info("test of %s successful", self )
            return True
        finally:
            with contextlib.suppress(FileNotFoundError):
                temp_dir.cleanup()

    def __repr__(self):
        return '%s(%s-%s)' % (self.__class__.__name__, self.service_name, self.name)


def _replace_from_env(env: dict, match: Match):
    if match.group(1):
        return '$'
    else:
        return env.get(match.group(2) or match.group(3))


def mklink(src, dst):
    try:
        os.symlink(src, dst)
    except OSError:
        try:
            os.link(src, dst)
        except OSError:
            shutil.copyfile(src, dst)
