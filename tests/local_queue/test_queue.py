import json
import socket
import unittest

from pybioas.scheduler.task_queue import QueueServer

try:
    import unittest.mock as mock
except ImportError:
    import mock

mock.patch.object = mock.patch.object


def run_counter_factory(num=1):
    counter = iter(range(num, -1, -1))

    # noinspection PyUnusedLocal
    def running(self):
        return bool(next(counter))
    return running


class TestServerSocket(unittest.TestCase):

    def setUp(self):
        self.socket_patch = mock.patch(
            'pybioas.scheduler.task_queue.socket',
            autospec=True
        )
        self.mock_socket = self.socket_patch.start()
        with mock.patch('pybioas.scheduler.task_queue.CommandFactory',
                        autospec=True):
            self.server = QueueServer('localhost', 0, mock.Mock(), mock.Mock())

        self.mock_client_socket = mock.Mock()
        self.mock_server_socket = mock.Mock()
        self.mock_server_socket.accept = mock.Mock(
            return_value=(self.mock_client_socket, '192.168.0.0:1234')
        )
        self.mock_socket.socket.return_value = self.mock_server_socket

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
        self.mock_client_socket.shutdown.\
            assert_called_once_with(self.mock_socket.SHUT_RDWR)
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


# noinspection PyTypeChecker
class TestServeClient(unittest.TestCase):

    def setUp(self):
        with mock.patch('pybioas.scheduler.task_queue.CommandFactory',
                        autospec=True):
            self.server = QueueServer('localhost', 0, mock.Mock(), mock.Mock())
        mock.patch.object(self.server, '_logger').start()

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
        conn = mock.Mock()
        conn.recv.return_value = QueueServer.HEAD_PING
        self.server._serve_client(conn)
        conn.send.assert_called_once_with(QueueServer.STATUS_OK)


# noinspection PyUnusedLocal
@mock.patch('pybioas.scheduler.task_queue.Job', autospec=True)
@mock.patch('pybioas.scheduler.task_queue.send_json')
@mock.patch('pybioas.scheduler.task_queue.recv_json')
class TestNewTaskRequest(unittest.TestCase):

    def setUp(self):
        self.add_job = mock.Mock()
        self.command_factory_patch = \
            mock.patch('pybioas.scheduler.task_queue.CommandFactory',
                       autospec=True)
        self.mock_command_factory = self.command_factory_patch.start()
        self.server = QueueServer('localhost', 0, mock.Mock(), self.add_job)
        self.conn = mock.create_autospec(socket.socket)
        self.conn.recv.return_value = QueueServer.HEAD_NEW_TASK

    def tearDown(self):
        self.command_factory_patch.stop()

    def test_successful_task_request(
            self, mock_recv_json, mock_send_json, mock_job_cls):
        """
        Tests how the client is served when the communication goes seamlessly
        and there is no exceptions.
        Server should send OK status response.
        Next, it should get the command class according to the specified
        service and create new command object with given options.
        A new job build with the command object should be passed to the
        `add_job` callback
        """
        mock_recv_json.return_value = {
            'service': mock.sentinel.service,
            'options': mock.sentinel.options
        }
        mock_command_cls = mock.Mock()
        self.mock_command_factory('nope.ini'). \
            get_command_class.return_value = mock_command_cls
        mock_command_cls.return_value = mock.sentinel.command

        self.server._serve_client(self.conn)

        self.conn.send.assert_called_once_with(QueueServer.STATUS_OK)
        self.mock_command_factory('nope.ini').get_command_class. \
            assert_called_once_with(mock.sentinel.service)
        mock_command_cls.assert_called_once_with(mock.sentinel.options)
        mock_job_cls.assert_called_once_with(mock.sentinel.command)
        self.add_job.assert_called_once_with(mock_job_cls(None))

    def test_invalid_json_handling(
            self, mock_recv_json, mock_send_json, mock_job_cls):
        """
        Tests how the client is server if given JSON is not valid.
        Error status should be sent back to the client.
        Client socket should be properly shut down and closed.
        Command should not be retrieved and job shouldn't be created.
        """
        mock_recv_json.side_effect = json.JSONDecodeError('mock', 'mock', 0)

        self.server._serve_client(self.conn)

        self.conn.send.assert_called_once_with(QueueServer.STATUS_ERROR)
        self.conn.shutdown.assert_called_once_with(socket.SHUT_RDWR)
        self.conn.close.assert_called_once_with()

        self.mock_command_factory.get_command_class.assert_not_called()
        mock_job_cls.assert_not_called()

    def test_malformed_json_object_handling(
            self, mock_recv_json, mock_send_json, mock_job_cls):
        """
        Tests the behaviour when data sent is a valid JSON (parseable)
        but it's object properties are invalid.
        """
        mock_recv_json.return_value = {}

        self.server._serve_client(self.conn)

        self.conn.send.assert_called_once_with(QueueServer.STATUS_ERROR)
        self.conn.shutdown.assert_called_once_with(socket.SHUT_RDWR)
        self.conn.close.assert_called_once_with()

        self.mock_command_factory.get_command_class.assert_not_called()
        mock_job_cls.assert_not_called()

    def test_connection_error(
            self, mock_recv_json, mock_send_json, mock_job_cls):
        """
        Tests the behaviour of client socket processing when the connection is
        suddenly aborted.
        """
        mock_recv_json.side_effect = OSError("Connection so broken. Wow.")

        self.server._serve_client(self.conn)

        self.conn.send.assert_called_once_with(QueueServer.STATUS_ERROR)
        self.conn.shutdown.assert_called_once_with(socket.SHUT_RDWR)
        self.conn.close.assert_called_once_with()

        self.mock_command_factory.get_local_command_class.assert_not_called()
        mock_job_cls.assert_not_called()

    def test_command_factory_failure(
            self, mock_recv_json, mock_send_json, mock_job_cls):
        """
        Test scenario when commands are not correctly configured and
        CommandFactory raises an exception.
        """
        # TODO build CommandFactory tests first and examine possible exceptions
