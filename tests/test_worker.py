import time
import unittest

from task_queue import queue_run, DeferredResult
from task_queue.job import JobStatus, JobResult
from . import dummy_task


class WorkerTest(unittest.TestCase):

    def test_worker(self):
        c = dummy_task.C()
        res = queue_run(c)
        self.assertIsInstance(res, DeferredResult)
        self.assertEqual(res.status, JobStatus.RUNNING)
        self.assertIsNone(res.result)
        time.sleep(1.2)
        self.assertEqual(res.status, JobStatus.COMPLETED)
        result = res.result
        self.assertIsInstance(result, JobResult)
        self.assertEqual(result.result, "Hello")
        self.assertIsNone(result.error)
