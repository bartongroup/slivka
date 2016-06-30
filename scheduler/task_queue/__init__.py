import socket

from . import utils
from .deferred_result import DeferredResult
from .exceptions import ConnectionError
from .worker import HOST, PORT, Worker


def queue_run(service, values):
    """
    Sends the task to the worker which enqueues it as a new job.
    :param service:
    :param values:
    :return: DeferredResult associated with the job
    :raise ConnectionError:
    """
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))
    client_socket.send(Worker.HEAD_NEW_TASK)

    utils.send_json(client_socket, {
        "service": service,
        "options": values
    })
    status = client_socket.recv(8)
    if status != Worker.STATUS_OK:
        raise ConnectionError("something bad happened")
    data = utils.recv_json(client_socket)
    job_id = data["jobId"]
    client_socket.close()
    return DeferredResult(job_id, (HOST, PORT))
