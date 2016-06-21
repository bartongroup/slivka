import time
import unittest

from scheduler.task_queue import (JobStatus, JobResult, queue_run,
                                  DeferredResult, RunnableTask)


class DummyTask(RunnableTask):

    def __init__(self, sleep=0, rvalue=None, exception=None):
        self._sleep = sleep
        self._rvalue = rvalue
        self._exception = exception

    def run(self, *args, **kwargs):
        time.sleep(self._sleep)
        if self._exception is not None:
            raise self._exception
        return self._rvalue


class WorkerTest(unittest.TestCase):
    """
    To run this test, worker must be running in a parallel process and
    be listening to incoming connections.
    """

    def test_deferred_result(self):
        t = DummyTask()
        res = queue_run(t)
        self.assertIsInstance(res, DeferredResult)

    def test_short_task(self):
        t = DummyTask()
        res = queue_run(t)
        time.sleep(0.1)
        self.assertEqual(res.status, JobStatus.COMPLETED)

    def test_long_task(self):
        t = DummyTask(sleep=1)
        res = queue_run(t)
        time.sleep(0.1)
        self.assertEqual(res.status, JobStatus.RUNNING)
        self.assertIsNone(res.result)
        time.sleep(1)
        self.assertEqual(res.status, JobStatus.COMPLETED)

    def test_return_value(self):
        t = DummyTask(rvalue="Hello World!")
        res = queue_run(t)
        time.sleep(0.1)
        self.assertEqual(res.result.result, "Hello World!")
        self.assertIsNone(res.result.error)

    def test_raise_exception(self):
        t = DummyTask(exception=ZeroDivisionError)
        res = queue_run(t)
        time.sleep(0.1)
        self.assertIsInstance(res.result.error, ZeroDivisionError)
        self.assertIsNone(res.result.result)
