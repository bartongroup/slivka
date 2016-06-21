import pickle
import socket

from . import utils
from .deferred_result import DeferredResult
from .job import JobStatus, JobResult
from .runnable_task import RunnableTask
from .worker import HOST, PORT, Worker


def queue_run(runnable):
    """
    Sends the task to the worker which enqueues it a new job.
    :param runnable: runnable task instance to be scheduled
    :return: DeferredResult associated with the job
    :raise ConnectionError
    """
    if not isinstance(runnable, RunnableTask):
        raise TypeError("Runnable must implement RunnableTask")
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))
    client_socket.send(Worker.MSG_NEW_TASK)

    runnable_string = pickle.dumps(runnable)

    client_socket.send(utils.numtobyte(len(runnable_string), 4))
    client_socket.send(runnable_string)
    status_code = client_socket.recv(4)
    if status_code != Worker.STATUS_OK:
        # TODO: compatibility warning: create exception class
        raise ConnectionError("Worker returned code: {0}"
                              .format(status_code.decode()))
    job_id = client_socket.recv(32).decode()
    client_socket.shutdown(socket.SHUT_RDWR)
    client_socket.close()

    return DeferredResult(job_id, (HOST, PORT))
