import filecmp
import os
import shutil
import sys
import tempfile
import time
import traceback
from functools import partial

import yaml

import slivka
from slivka.scheduler.core import RunnerSelector
from slivka.scheduler import Runner, RunInfo

selector = RunnerSelector()
for service in slivka.settings.services.values():
    selector.add_runners(service.name, service.command)


RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
REGULAR = "\033[0m"


def colored(text, color):
    return color + text + REGULAR


def test_all(directory, cleanup_work_dir=True):
    global print
    success = 0
    for file in os.scandir(directory):
        if not file.is_file(): continue
        test_name, _ = os.path.splitext(file.name)
        print('Running test for', test_name)
        old_print = print
        print = partial(print, file=sys.stderr)
        try:
            ret = run_test(file.path, cleanup_work_dir)
            success |= ret
        except Exception:
            traceback.print_exc()
            old_print('%s:' % test_name, colored("ERROR", RED))
            success |= 128
        else:
            state = colored('OK', GREEN) if ret == 0 else colored('FAIL', YELLOW)
            old_print('%s:' % test_name, state)
        finally:
            print = old_print
    return 0


def run_test(file_path, cleanup_work_dir=True):
    test_dir = os.path.dirname(file_path)
    data = yaml.safe_load(open(file_path))
    try:
        runner = selector.runners[data['service'], data['runner']]
    except KeyError:
        print("Runner %(service)s:%(runner)s does not exist." % data)
        return 1
    try:
        job = start_job(runner, data['inputs'], test_dir)
    except Exception as e:
        print("Job submission failed with error", repr(e))
        traceback.print_exc()
        return 2
    try:
        wait_for_completion(runner, job, data.get('timeout'))
    except TimeoutError:
        print("Job timed out.")
        return 4
    except Exception as e:
        print("Exception raised when retrieving job status", repr(e))
        traceback.print_exc()
        return 8
    output_error = False
    for outfile, error in check_output(test_dir, job.cwd, data['outputs']):
        if isinstance(error, FileNotFoundError):
            print("Output file %s not found." % outfile)
        elif isinstance(error, ContentsNotMatchingError):
            print("Content of %s does not match %s" % (outfile, error.path))
        else:
            print(outfile, error)
        output_error = True
    if cleanup_work_dir:
        shutil.rmtree(job.cwd)
    return 16 if output_error else 0


def start_job(runner: Runner, inputs: dict, test_dir: str):
    inputs = inputs.copy()
    for name, value in inputs.items():
        if runner.inputs[name].get('type') == 'file':
            inputs[name] = os.path.join(test_dir, value)
    work_dir = tempfile.mkdtemp(dir=test_dir)
    job = runner.run(inputs, work_dir)
    return job


def wait_for_completion(runner: Runner, job: RunInfo, timeout=None):
    if timeout is None:
        timeout = 8640000
    end_time = time.time() + timeout
    while time.time() <= end_time:
        state = runner.check_status(job.id, job.cwd)
        if state.is_finished():
            return state
        time.sleep(0.5)
    else:
        raise TimeoutError


class ContentsNotMatchingError(Exception):
    def __init__(self, path):
        super().__init__(path)
        self.path = path


def check_output(test_dir, work_dir, outputs):
    for output in outputs:
        out_path = os.path.join(work_dir, output['filename'])
        if not os.path.isfile(out_path):
            yield (os.path.relpath(out_path, test_dir), FileNotFoundError())
            continue
        cmp_path = output.get('matches')
        if cmp_path is None:
            continue
        cmp_path = os.path.join(test_dir, cmp_path)
        if not filecmp.cmp(cmp_path, out_path, False):
            yield (
                os.path.relpath(out_path, test_dir),
                ContentsNotMatchingError(os.path.relpath(cmp_path, test_dir))
            )
            continue
