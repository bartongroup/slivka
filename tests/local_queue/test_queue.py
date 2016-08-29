import logging
import sys
import types
import unittest

from pybioas.scheduler.exc import JobNotFoundError
from pybioas.scheduler.task_queue import QueueServer, TaskQueue, KILL_WORKER

try:
    import unittest.mock as mock
except ImportError:
    import mock

mock.patch.object = mock.patch.object

logging.basicConfig(level=logging.CRITICAL)


class TestTaskQueueBase(unittest.TestCase):

    NUM_WORKERS = 3

    # noinspection PyMethodOverriding
    @mock.patch('pybioas.scheduler.task_queue.queue.Queue')
    @mock.patch('pybioas.scheduler.task_queue.QueueServer', autospec=True)
    @mock.patch('pybioas.scheduler.task_queue.Worker', autospec=True)
    def setUp(self, mock_worker, mock_server, mock_queue):
        self.mock_worker_cls = mock_worker
        self.mock_server_cls = mock_server
        self.mock_worker = mock_worker.return_value
        self.mock_server = mock_server.return_value
        self.mock_queue = mock_queue.return_value
        self.task_queue = TaskQueue(
            mock.sentinel.host,
            mock.sentinel.port,
            num_workers=self.NUM_WORKERS
        )

    def test_init(self):
        self.assertEqual(self.mock_worker_cls.call_count, self.NUM_WORKERS)
        self.mock_worker_cls.assert_called_with(self.mock_queue)
        self.mock_server_cls.assert_called_once_with(
            mock.sentinel.host,
            mock.sentinel.port,
            mock.ANY,
            mock.ANY
        )

    def test_queue_access(self):
        ((_, _, get, add), _) = self.mock_server_cls.call_args
        job_id = add(mock.sentinel.job)
        job = get(job_id)
        self.assertEqual(job, mock.sentinel.job)
        self.mock_queue.put.assert_called_once_with(mock.sentinel.job)

    def test_start(self):
        self.task_queue.start(True)
        self.mock_server.start.assert_called_once_with()
        self.assertEqual(self.mock_worker.start.call_count, self.NUM_WORKERS)

    def test_shutdown(self):
        self.mock_queue.unfinished_tasks = 1
        self.mock_worker.is_alive.return_value = True
        self.task_queue.shutdown()
        self.assertEqual(self.mock_queue.unfinished_tasks, 1 + self.NUM_WORKERS)
        self.mock_queue.queue.extend.assert_called_once_with(
            [KILL_WORKER] * self.NUM_WORKERS
        )
        self.mock_server.shutdown.assert_called_once_with()


class TestServerCommunication(unittest.TestCase):

    ADDRESS = ('localhost', 2354)

    def setUp(self):
        self.mock_get = mock.MagicMock(types.FunctionType)
        self.mock_add = mock.MagicMock(types.FunctionType)
        self.server = QueueServer(
            self.ADDRESS[0], self.ADDRESS[1], self.mock_get, self.mock_add
        )
        self.server.start()
        while not self.server.running:
            pass

    def tearDown(self):
        self.server.shutdown()
        self.server.join()

    def test_check_connection_ok(self):
        status = QueueServer.check_connection(self.ADDRESS)
        self.assertTrue(status)

    def test_check_connection_server_down(self):
        status = QueueServer.check_connection((self.ADDRESS[0], 1001))
        self.assertFalse(status)

    def test_check_connection_failure(self):
        # noinspection PyUnusedLocal
        def mock_serve_client(this, header, request):
            return this.STATUS_ERROR

        # noinspection PyUnresolvedReferences
        with mock.patch.object(self.server, 'handle_request',
                               new=mock_serve_client.__get__(self.server)):
            status = QueueServer.check_connection(self.ADDRESS)
        self.assertFalse(status)

    @mock.patch('pybioas.scheduler.task_queue.LocalCommand')
    def test_job_submission(self, mock_local_cmd):
        self.mock_add.return_value = 1
        job_id = QueueServer.submit_job(
            cmd=['mock.sentinel.cmd'],
            cwd='mock.sentinel.cwd',
            env={'MOCK': 'mock.sentinel.env'},
            address=self.ADDRESS
        )
        self.assertEqual(job_id, 1)
        mock_local_cmd.assert_called_once_with(
            cmd=['mock.sentinel.cmd'],
            cwd='mock.sentinel.cwd',
            env={'MOCK': 'mock.sentinel.env'}
        )
        self.mock_add.assert_called_once_with(mock_local_cmd.return_value)

    def test_job_submission_server_down_oserror(self):
        with self.assertRaises(OSError):
            QueueServer.submit_job(
                cmd=['mock.sentinel.cmd'],
                cwd='mock.sentinel.cwd',
                env={'MOCK': 'mock.sentinel.env'},
                address=(self.ADDRESS[0], 1234)
            )

    @unittest.skipIf(sys.version_info <= (3, 2),
                     "ConnectionRefusedError in python 3.3")
    def test_job_submission_server_down(self):
        with self.assertRaises(ConnectionRefusedError):
            QueueServer.submit_job(
                cmd=['mock.sentinel.cmd'],
                cwd='mock.sentinel.cwd',
                env={'MOCK': 'mock.sentinel.env'},
                address=(self.ADDRESS[0], 1234)
            )

    def test_job_status(self):
        self.mock_get.return_value.status = 'mock_success'
        status = QueueServer.get_job_status(15, address=self.ADDRESS)
        self.assertEqual(status, 'mock_success')
        self.mock_get.assert_called_once_with(15)

    def test_job_status_server_down_oserror(self):
        with self.assertRaises(OSError):
            QueueServer.get_job_status(1, address=('localhost', 1234))

    @unittest.skipIf(sys.version_info <= (3, 2),
                     "ConnectionRefusedError in python 3.3")
    def test_job_status_server_down(self):
        with self.assertRaises(ConnectionRefusedError):
            QueueServer.get_job_status(1, address=('localhost', 1234))

    def test_job_status_not_exist(self):
        self.mock_get.return_value = None
        with self.assertRaises(JobNotFoundError):
            QueueServer.get_job_status(15, address=self.ADDRESS)

    def test_job_output(self):
        self.mock_get.return_value.return_code = '13'
        out = QueueServer.get_job_return_code(14, address=self.ADDRESS)
        self.assertEqual(out, '13')
        self.mock_get.assert_called_once_with(14)

    def test_job_output_not_exist(self):
        self.mock_get.return_value = None
        with self.assertRaises(JobNotFoundError):
            QueueServer.get_job_return_code(14, address=self.ADDRESS)
