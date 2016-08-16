import json
import logging
import socket
import sys
import types
import unittest

from pybioas.scheduler.exc import ServerError
from pybioas.scheduler.task_queue import QueueServer, TaskQueue, KILL_WORKER, \
    ProcessOutput

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


def run_counter_factory(num=1):
    counter = iter(range(num, -1, -1))

    # noinspection PyUnusedLocal
    def running(self):
        return bool(next(counter))
    return running


class TestServerSocket(unittest.TestCase):

    def setUp(self):
        self.mock_get_job = mock.Mock(types.MethodType)
        self.mock_add_job = mock.Mock(types.MethodType)
        self.server = QueueServer(
            'localhost', 0, self.mock_get_job, self.mock_add_job)

        self.socket_patch = mock.patch(
            'pybioas.scheduler.task_queue.socket', autospec=True)
        self.mock_socket_module = self.socket_patch.start()
        self.mock_client_socket = mock.create_autospec(socket.socket)
        self.mock_server_socket = mock.create_autospec(socket.socket)
        self.mock_server_socket.accept.return_value = \
            (self.mock_client_socket, '192.168.0.0:1234')
        self.mock_socket_module.socket.return_value = self.mock_server_socket

        self.serve_patch = mock.patch.object(self.server, '_serve_client')
        self.mock_serve_client = self.serve_patch.start()

    def tearDown(self):
        self.socket_patch.stop()
        self.serve_patch.stop()

    def test_socket_closed(self):
        """
        Tests if the server socket is correctly closed in normal conditions.
        """
        running = run_counter_factory(2)
        with mock.patch.object(QueueServer, 'running', property(running)):
            self.server.run()
        self.mock_server_socket.close.assert_called_once_with()

    def test_client_socket_closed(self):
        """
        Tests if the client socket is closed when the shutdown signal is
        received while opening connection.
        """
        running = run_counter_factory(1)
        with mock.patch.object(QueueServer, 'running', property(running)):
            self.server.run()
        self.mock_client_socket.shutdown. \
            assert_called_once_with(self.mock_socket_module.SHUT_RDWR)
        self.mock_client_socket.close.assert_called_once_with()

    def test_serve_client_started(self):
        """
        Tests if the serve client method was called after receiving the
        connection from the client.
        """
        running = run_counter_factory(2)
        with mock.patch.object(QueueServer, 'running', property(running)):
            self.server.run()
        self.mock_serve_client.assert_called_once_with(self.mock_client_socket)

    def test_serve_client_not_started(self):
        """
        Tests if serving client was not started when the shutdown is in
        process.
        """
        running = run_counter_factory(1)
        with mock.patch.object(QueueServer, 'running', property(running)):
            self.server.run()
        self.mock_serve_client.assert_not_called()


class TestServeClient(unittest.TestCase):

    def setUp(self):
        self.server = QueueServer(
            'localhost', 0,
            mock.Mock(types.FunctionType),
            mock.Mock(types.FunctionType)
        )

    def test_timeout_socket_close(self):
        """
        Checks if the client socket is properly closed when connection times
        out.
        """
        conn = mock.create_autospec(socket.socket)
        conn.recv.side_effect = socket.timeout
        self.server._serve_client(conn)
        conn.shutdown.assert_called_once_with(socket.SHUT_RDWR)
        conn.close.assert_called_once_with()

    def test_disconnected_socket_close(self):
        """
        Checks if the client socket is properly closed when connection error
        occurs.
        """
        conn = mock.create_autospec(socket.socket)
        conn.recv.side_effect = OSError("Connection refused.")
        self.server._serve_client(conn)
        conn.shutdown.assert_called_once_with(socket.SHUT_RDWR)
        conn.close.assert_called_once_with()

    def test_socket_close(self):
        """
        Checks if the socket is closed properly after the connection.
        """
        conn = mock.create_autospec(socket.socket)
        conn.recv.return_value = QueueServer.HEAD_PING
        self.server._serve_client(conn)
        conn.shutdown.assert_called_once_with(socket.SHUT_RDWR)
        conn.close.assert_called_once_with()

    def test_ping_request(self):
        """
        Tests if the server responds to PING message with OK status.
        """
        conn = mock.create_autospec(socket.socket)
        conn.recv.return_value = QueueServer.HEAD_PING
        self.server._serve_client(conn)
        conn.send.assert_called_once_with(QueueServer.STATUS_OK)


class TestServerCommunication(unittest.TestCase):

    PORT = 2354

    def setUp(self):
        self.mock_get = mock.MagicMock(types.FunctionType)
        self.mock_add = mock.MagicMock(types.FunctionType)
        self.server = QueueServer(
            'localhost', self.PORT, self.mock_get, self.mock_add
        )
        self.server.start()
        while not self.server.running:
            pass

    def tearDown(self):
        self.server.shutdown()
        self.server.join()

    def test_check_connection_ok(self):
        status = QueueServer.check_connection('localhost', self.PORT)
        self.assertTrue(status)

    def test_check_connection_server_down(self):
        status = QueueServer.check_connection('localhost', 0000)
        self.assertFalse(status)

    def test_check_connection_failure(self):
        def mock_serve_client(this, conn):
            conn.send(this.STATUS_ERROR)
            conn.close()

        # noinspection PyUnresolvedReferences
        with mock.patch.object(self.server, '_serve_client',
                               new=mock_serve_client.__get__(self.server)):
            status = QueueServer.check_connection('localhost', self.PORT)
        self.assertFalse(status)

    @mock.patch('pybioas.scheduler.task_queue.LocalCommand')
    def test_job_submission(self, mock_local_cmd):
        self.mock_add.return_value = 1
        job_id = QueueServer.submit_job(
            cmd=['mock.sentinel.cmd'],
            cwd='mock.sentinel.cwd',
            env={'MOCK': 'mock.sentinel.env'},
            host='localhost',
            port=self.PORT
        )
        self.assertEqual(job_id, 1)
        mock_local_cmd.assert_called_once_with(
            cmd=['mock.sentinel.cmd'],
            cwd='mock.sentinel.cwd',
            env={'MOCK': 'mock.sentinel.env'}
        )
        self.mock_add.assert_called_once_with(mock_local_cmd.return_value)

    @mock.patch('pybioas.scheduler.task_queue.recv_json')
    @mock.patch('pybioas.scheduler.task_queue.LocalCommand')
    def test_job_submission_invalid_json(self, mock_local_cmd, mock_recv_json):
        mock_recv_json.side_effect = json.JSONDecodeError('foo', 'bar', 0)
        with self.assertRaises(ServerError):
            QueueServer.submit_job(
                cmd=['mock.sentinel.cmd'],
                cwd='mock.sentinel.cwd',
                env={'MOCK': 'mock.sentinel.env'},
                host='localhost',
                port=self.PORT
            )
        mock_local_cmd.assert_not_called()
        self.mock_add.assert_not_called()

    def test_job_submission_server_down_oserror(self):
        with self.assertRaises(OSError):
            QueueServer.submit_job(
                cmd=['mock.sentinel.cmd'],
                cwd='mock.sentinel.cwd',
                env={'MOCK': 'mock.sentinel.env'},
                host='localhost',
                port=0000
            )

    @unittest.skipIf(sys.version_info <= (3, 2),
                     "ConnectionRefusedError in python 3.3")
    def test_job_submission_server_down(self):
        with self.assertRaises(ConnectionRefusedError):
            QueueServer.submit_job(
                cmd=['mock.sentinel.cmd'],
                cwd='mock.sentinel.cwd',
                env={'MOCK': 'mock.sentinel.env'},
                host='localhost',
                port=1234
            )

    def test_job_status(self):
        self.mock_get.return_value.status = 'mock_success'
        status = QueueServer.get_job_status(
            15, host='localhost', port=self.PORT)
        self.assertEqual(status, 'mock_success')
        self.mock_get.assert_called_once_with(15)

    def test_job_status_server_down_oserror(self):
        with self.assertRaises(OSError):
            QueueServer.get_job_status(1, host='localhost', port=1234)

    @unittest.skipIf(sys.version_info <= (3, 2),
                     "ConnectionRefusedError in python 3.3")
    def test_job_status_server_down(self):
        with self.assertRaises(ConnectionRefusedError):
            QueueServer.get_job_status(1, host='localhost', port=1234)

    def test_job_status_not_exist(self):
        self.mock_get.return_value = None
        with self.assertRaises(ServerError):
            QueueServer.get_job_status(15, host='localhost', port=self.PORT)

    def test_job_output(self):
        process_output = ProcessOutput(0, 'mock_stdout', 'mock_stderr')
        self.mock_get.return_value.output = process_output
        out = QueueServer.get_job_output(14, host='localhost', port=self.PORT)
        self.assertTupleEqual(out, process_output)
        self.mock_get.assert_called_once_with(14)

    def test_job_output_not_exist(self):
        self.mock_get.return_value = None
        with self.assertRaises(ServerError):
            QueueServer.get_job_output(14, host='localhost', port=self.PORT)
