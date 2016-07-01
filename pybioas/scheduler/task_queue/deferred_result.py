import socket

from . import utils
from .exceptions import ConnectionError
from .worker import Worker


class DeferredResult:
    """
    Deferred result instances are intermediate objects which communicates
    between client and the task queue. When the job is queued, it returns
    Deferred result instead of job result which is not available yet.
    It allows asynchronous execution of the task and retrieving the result
    when the job is complete.

    DeferredResult should not be instantiated directly, but through calling
    `scheduler.task_queue.queue_run`.
    """

    def __init__(self, job_id, server_address):
        """
        :param job_id: identification of the task.
        :param server_address: tuple of address and port of the worker server
        """
        self.job_id = job_id
        self.server_address = server_address

    @property
    def status(self):
        """
        Asks the server for the status of the job linked to this deferred
        result instance.
        :return: current job status
        :rtype: enum job.JobStatus value
        """
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(self.server_address)

        client_socket.send(Worker.HEAD_JOB_STATUS)
        utils.send_json(client_socket, {"jobId": self.job_id})
        status = client_socket.recv(8)
        if status != Worker.STATUS_OK:
            raise ConnectionError("something bad happened")
        data = utils.recv_json(client_socket)
        client_socket.close()
        return data['status']

    @property
    def result(self):
        """
        Asks the server for the result of the job associated with this
        deferred result.
        :return: job result or exception traceback if failed
        """
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(self.server_address)

        client_socket.send(Worker.HEAD_JOB_RESULT)
        utils.send_json(client_socket, {"jobId": self.job_id})
        status = client_socket.recv(8)
        if status != Worker.STATUS_OK:
            raise ConnectionError("something bad happened")
        data = utils.recv_json(client_socket)
        client_socket.close()
        return data

    def __repr__(self):
        return ("<DeferredResult {job_id} server={addr[0]}:{addr[1]}>"
                .format(job_id=self.job_id, addr=self.server_address))
