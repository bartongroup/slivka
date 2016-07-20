import queue
import socket
import tempfile
import threading
import time
import unittest
try:
    import unittest.mock as mock
except ImportError:
    import mock

from pybioas.scheduler.task_queue.task_queue import (
    TaskQueue, Worker, QueueServer, KILL_WORKER, HOST, PORT
)


class TestWorker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import pybioas.config

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
        for i in range(5):
            self.q.put(mock.Mock())
        stop = time.time() + 1
        while self.q.unfinished_tasks and time.time() < stop:
            time.sleep(0.001)
        self.assertEqual(self.q.unfinished_tasks, 0)

    def test_kill_worker(self):
        self.q.put(KILL_WORKER)
        stop = time.time() + 1
        while self.worker.is_alive() and time.time() < stop:
            time.sleep(0.001)
        self.assertFalse(self.worker.is_alive())

    def test_execution(self):
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


class TestTaskQueue(unittest.TestCase):

    task_queue = None  # type: TaskQueue
    server_thread = None  # type: threading.Thread

    @classmethod
    def setUpClass(cls):
        cls.task_queue = TaskQueue(num_workers=1)
        cls.task_queue.start(async=True)

    def test_check_connection(self):
        self.assertTrue(QueueServer.check_connection())

    def test_ping(self):
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((HOST, PORT))
        conn.send(TaskQueue.HEAD_PING)
        status = conn.recv(8)
        self.assertEqual(status, TaskQueue.STATUS_OK)

    @classmethod
    def tearDownClass(cls):
        cls.task_queue.shutdown()
