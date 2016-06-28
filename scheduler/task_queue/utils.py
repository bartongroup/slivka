import inspect
import json
import weakref


def bytetonum(byte_string):
    """
    Converts bytes string to the integer number. First byte is the most
    significant byte. Each byte is a digit and uses a numeric system of
    base 256.
    :param byte_string: string of bytes to be translated to number
    :return: number represented in a 256 base bytes string
    """
    msb = len(byte_string)
    return sum(
        b * (256 ** n)
        for (b, n) in zip(bytearray(byte_string), reversed(range(msb)))
    )


def numtobyte(number, length=0):
    """
    Converts a number into a byte string of digits using the 256 base system.
    :param number: converted number
    :param length: the length the string will be extended to if shorter
    :return: string of bytes encoding the number using 256 base system
    """
    digits = []
    while number > 0:
        digits.append(number % 256)
        number //= 256
    b = bytes(reversed(digits))
    return b'\x00' * (length - len(b)) + b


def recv_json(conn):
    """
    Receives json data from the socket. Json must be sent using complementary
    function `send_json`.
    :param conn: active socket connection
    :return: loaded json object
    :raise json.JSONDecodeError: content can't be decoded
    :raise socket.timeout: connection timed out
    """
    content_length = bytetonum(conn.recv(4))
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
    conn.send(numtobyte(content_length, 4))
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
