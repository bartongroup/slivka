import pickle
import socket
import threading
import uuid

from collections import namedtuple

from .worker import HOST, PORT


class Job:
    def __init__(self, func, args=None, kwargs=None):
        """
        :param func: target function to be executed bo the worker
        :param args: arguments passed to the target function
        :param kwargs: keyword arguments passed to the target funciton
        """
        self.status = JobStatus.PENDING
        self.func = func
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.id = uuid.uuid4().hex
        self._result = None
        self._finished_slot = None

    def set_finished_slot(self, slot):
        """
        Sets the callable to be executed when the job is complete.
        :param slot: callable to be executed
        """
        self._finished_slot = slot

    def _send_finished_signal(self):
        """
        Sends a finished signal to the slot when the job is complete
        """
        if self._finished_slot:
            self._finished_slot()

    def start(self):
        """
        Launches a new thread where the target function is executed
        :return: id of the job
        """
        if not self.is_pending():
            raise RuntimeError("Job is already running")
        thread = threading.Thread(
            target=self._execute,
            args=self.args,
            kwargs=self.kwargs
        )
        thread.start()
        return self.id

    def _execute(self):
        """
        Executes the target function.
        """
        self.status = JobStatus.RUNNING
        try:
            self._result = self.func(*self.args, **self.kwargs)
        except Exception as e:
            self._exception = e
            self.status = JobStatus.FAILED
            raise
        else:
            self.status = JobStatus.COMPLETED
        finally:
            self._send_finished_signal()

    def terminate(self):
        raise NotImplementedError()

    @property
    def result(self):
        if not self.is_finished():
            raise RuntimeWarning("Job is not finished")
        return JobResult(self._result, self._exception)

    def is_finished(self):
        return (self.status == JobStatus.PENDING or
                self.status == JobStatus.RUNNING)

    def is_pending(self):
        return self.status == JobStatus.PENDING

    def is_running(self):
        return self.status == JobStatus.RUNNING


class JobStatus:
    PENDING = "PENDING",
    RUNNING = "RUNNING",
    COMPLETED = "COMPLETED",
    FAILED = "FAILED"


JobResult = namedtuple("JobResult", ["result", "error"])


def queue_run(runnable, *args, **kwargs):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))

    runnable_string = pickle.dumps(runnable)
    args_string = pickle.dumps(args)
    kwargs_string = pickle.dumps(kwargs)

    client_socket.send(runnable_string)
    client_socket.recv(1)
    client_socket.send(args_string)
    client_socket.recv(1)
    client_socket.send(kwargs_string)
    client_socket.recv(1)

    status_code = client_socket.recv(4)
    job_id = client_socket.recv(64)
    client_socket.close()

    return status_code, job_id
