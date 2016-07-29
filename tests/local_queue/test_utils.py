import socket
import unittest
try:
    import unittest.mock as mock
except ImportError:
    import mock
from io import BytesIO

from pybioas.scheduler import recv_json, send_json


class TestJsonTransfer(unittest.TestCase):

    def test_send_recv(self):
        data_dict = {
            'foo': 'bar',
            'qux': 'quz'
        }
        buffer = BytesIO()
        mock_socket = mock.create_autospec(socket.socket)
        mock_socket.send = buffer.write
        send_json(mock_socket, data_dict)
        buffer.seek(0)
        mock_socket.recv = buffer.read
        received_data = recv_json(mock_socket)
        self.assertDictEqual(received_data, data_dict)
