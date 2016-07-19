import inspect
import json
import logging
import os
import weakref

import pybioas


def recv_json(conn):
    """
    Receives json data from the socket. Json must be sent using complementary
    function `send_json`.
    :param conn: active socket connection
    :return: loaded json object
    :raise json.JSONDecodeError: content can't be decoded
    :raise socket.timeout: connection timed out
    """
    content_length = int.from_bytes(conn.recv(8), 'big')
    content = conn.recv(content_length).decode()
    return json.loads(content)


def send_json(conn, data):
    """
    Sends encoded json object through the socket. It can be received with
    complementary function `recv_json`
    :param conn: active socket connection
    :param data: json object to be sent
    :return: number of bytes sent
    :raise TypeError: data is not JSON serializable
    """
    content = json.dumps(data).encode()
    content_length = len(content)
    conn.send(content_length.to_bytes(8, 'big'))
    return conn.send(content)


class Signal(object):

    def __init__(self):
        self._functions = set()
        self._methods = set()

    def __call__(self, *args, **kwargs):
        for func in self._functions:
            func(*args, **kwargs)
        for weak_method in self._methods:
            method = weak_method()
            method and method(*args, **kwargs)

    def call(self, *args, **kwargs):
        return self.__call__(*args, **kwargs)

    def register(self, slot):
        if inspect.ismethod(slot):
            self._methods.add(weakref.WeakMethod(slot))
        else:
            self._functions.add(slot)


_logger = None

def get_logger():
    global _logger
    if _logger is None:
        _logger = logging.getLogger(__name__)
        _logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s TaskQueue %(levelname)s: %(message)s",
            "%d %b %H:%M:%S"
        )

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        _logger.addHandler(stream_handler)

        file_handler = logging.FileHandler(
            os.path.join(pybioas.settings.BASE_DIR, "TaskQueue.log"))
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)
    return _logger
