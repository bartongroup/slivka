import queue
import tempfile
import time
import unittest
from unittest import mock as mock

import pybioas.config
from pybioas.scheduler.task_queue.task_queue import Worker, KILL_WORKER


class TestWorker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        temp_dir = tempfile.TemporaryDirectory()
        settings = mock.Mock(
            BASE_DIR=temp_dir.name,
            MEDIA_DIR=".",
            SECRET_KEY=b'\x00',
            SERVICE_INI=None
        )
        pybioas.settings = pybioas.config.Settings(settings)

    def setUp(self):
        self.q = queue.Queue()
        self.worker = Worker(self.q)
        self.worker.start()

    def test_task_done(self):
        """
        Tests if worker marks all tasks as finished.
        """
        for i in range(5):
            self.q.put(mock.Mock())
        stop = time.time() + 1
        while self.q.unfinished_tasks and time.time() < stop:
            time.sleep(0.001)
        self.assertEqual(self.q.unfinished_tasks, 0)

    def test_kill_worker(self):
        """
        Tests if picking KILL WORKER stops worker from running.
        """
        self.q.put(KILL_WORKER)
        stop = time.time() + 1
        while self.worker.is_alive() and time.time() < stop:
            time.sleep(0.001)
        self.assertFalse(self.worker.is_alive())

    def test_execution(self):
        """
        Tests if job was executed by the worker exactly once.
        """
        job = mock.Mock()
        self.q.put(job)
        stop = time.time() + 1
        while not job.run.called and time.time() < stop:
            time.sleep(0.001)
        job.run.assert_called_once_with()

    def tearDown(self):
        while True:
            try:
                self.q.get_nowait()
                self.q.task_done()
            except queue.Empty:
                break
        while self.q.empty():
            self.q.put(KILL_WORKER)
            time.sleep(0.01)
