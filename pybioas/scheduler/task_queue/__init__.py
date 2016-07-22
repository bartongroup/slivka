import socket

import pybioas
from . import utils
from .deferred_result import DeferredResult
from .exceptions import ServerError
from .task_queue import TaskQueue, QueueServer


def queue_run(service, values):
    """
    Sends the task to the worker which enqueues it as a new job.
    :param service: name of service configuration
    :param values: options passed to the configuration
    :return: DeferredResult associated with the job
    :raise ServerError: server can't process the request
    :raise OSError: connection with server failed
    """
    address = (pybioas.settings.QUEUE_HOST, pybioas.settings.QUEUE_PORT)
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(address)
    client_socket.send(TaskQueue.HEAD_NEW_TASK)

    utils.send_json(client_socket, {
        "service": service,
        "options": values
    })
    status = client_socket.recv(8)
    if status != TaskQueue.STATUS_OK:
        raise ServerError("something bad happened")
    data = utils.recv_json(client_socket)
    job_id = data["jobId"]
    client_socket.shutdown(socket.SHUT_RDWR)
    client_socket.close()
    return DeferredResult(job_id, address)
