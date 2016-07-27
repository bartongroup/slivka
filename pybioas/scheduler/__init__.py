import io
import json


def recv_json(conn):
    """
    Receives json data from the socket. Json must be sent using complementary
    function `send_json`.
    :param conn: active socket connection
    :type conn: socket.socket
    :return: loaded json object
    :raise json.JSONDecodeError: content can't be decoded
    :raise socket.timeout: connection timed out
    """
    content_length = int.from_bytes(conn.recv(8), 'big')
    buffer = io.BytesIO()
    remaining = content_length
    while remaining > 0:
        recv_length = min(remaining, 16384)
        content = conn.recv(recv_length)
        if not content:
            break
        remaining -= buffer.write(content)
    buffer.seek(0)
    return json.loads(buffer.read().decode())


def send_json(conn, data):
    """
    Sends encoded json object through the socket. It can be received with
    complementary function `recv_json`
    :param conn: active socket connection
    :type conn: socket.socket
    :param data: json object to be sent
    :type data: dict
    :return: number of bytes sent
    :raise TypeError: data is not JSON serializable
    """
    content = json.dumps(data).encode()
    content_length = len(content)
    conn.send(content_length.to_bytes(8, 'big'))
    return conn.send(content)
