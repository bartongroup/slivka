import inspect
import itertools
import json
import logging
import queue
import socket
import threading
import time
import uuid
import weakref

import pybioas
from pybioas.scheduler import recv_json, send_json
from pybioas.scheduler.command import CommandFactory


class TaskQueue:
    # Headers and status codes. Each is eight bytes long.

    def __init__(self, host=None, port=None, num_workers=4):
        """
        :param host: server host address
        :param port: server port
        :param num_workers: number of concurrent workers to spawn
        """
        if host is None: host = pybioas.settings.QUEUE_HOST
        if port is None: port = pybioas.settings.QUEUE_PORT
        self._logger = logging.getLogger(__name__)
        self._queue = queue.Queue()
        self._jobs = dict()
        self._workers = [Worker(self._queue) for _ in range(num_workers)]
        self._server = QueueServer(host, port, self._jobs.get, self._queue_job)

    def start(self, async=False):
        """
        Launches the task queue. Starts the server thread and starts all
        worker threads. Then it waits for KeyboardInterrupt signal
        to stop execution of the server and workers.
        Waits for all threads to join before exiting.
        """
        self._logger.debug("Starting server.")
        self._server.start()
        self._logger.debug("Starting workers.")
        for worker in self._workers:
            worker.start()
        if async:
            return
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            self._logger.info("Shutting down...")
            self.shutdown()

    def shutdown(self):
        """
        Flushes the task queue and puts kill worker signal for each
        alive worker.
        Then, pokes the server to stop listening and return.
        :return:
        """
        self._logger.debug("Shutdown signal.")

        self._logger.debug("Shutting down the server.")
        self._server.shutdown()

        num_workers = sum(worker.is_alive() for worker in self._workers)
        self._logger.debug("Sending %d KILLS to workers.", num_workers)
        with self._queue.mutex:
            self._queue.unfinished_tasks -= len(self._queue.queue)
            self._queue.queue.clear()
            self._queue.queue.extend([KILL_WORKER] * num_workers)
            self._queue.unfinished_tasks += num_workers
            self._queue.not_empty.notify_all()

        self._server.join()
        self._logger.debug("Server thread joined.")
        for worker in self._workers:
            worker.join()
        self._logger.debug("Workers joined.")

    def _queue_job(self, job):
        """
        Adds a new job to the queue and registers "finished" signal.
        :param job: new job
        :type job: Job
        """
        job.sig_finished.register(self._on_job_finished)
        self._logger.debug("Adding job %s to queue.", job)
        self._jobs[job.id] = job
        self._queue.put(job)

    def _on_job_finished(self, job_id):
        """
        Callback slot activated when the job is finished.
        :param job_id: id of the job which sent the signal
        """
        self._logger.info('%s finished', self._jobs[job_id])


KILL_WORKER = 'KILL'


class Worker(threading.Thread):

    _counter = itertools.count(1)

    def __init__(self, jobs_queue):
        """
        :param jobs_queue: queue with the jobs to execute
        :type jobs_queue: queue.Queue[Job]
        """
        super(Worker, self).__init__(name="Worker-%d" % next(self._counter))
        self._logger = logging.getLogger(__name__)
        self._queue = jobs_queue
        self._job = None

    def run(self):
        self._logger.debug("%s started.", self.name)
        while True:
            self._job = self._queue.get()
            self._logger.debug("%s picked up %s", self.name, self._job)
            # noinspection PyBroadException
            try:
                if self._job == KILL_WORKER:
                    break
                else:
                    self._job.run()
            except:
                self._logger.exception("Critical error.")
            finally:
                self._queue.task_done()
                self._job = None
        self._logger.debug("%s died.", self.name)


class QueueServer(threading.Thread):

    HEAD_NEW_TASK = b'NEW TASK'
    HEAD_JOB_STATUS = b'JOB STAT'
    HEAD_JOB_RESULT = b'JOB RES '
    HEAD_PING = b'PING    '
    STATUS_OK = b'OK      '
    STATUS_ERROR = b'ERROR   '

    def __init__(self, host, port, get_job, add_job):
        super(QueueServer, self).__init__(name='QueueServer')
        self._logger = logging.getLogger(__name__)
        self._running = True
        self._host = host
        self._port = port
        self._get_job = get_job
        self._add_job = add_job
        self._server_socket = None
        self.command_factory = CommandFactory(pybioas.settings.SERVICE_INI)

    def run(self):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind((self._host, self._port))
        self._server_socket.settimeout(5)
        self._server_socket.listen(5)
        self._logger.info("Ready to accept connections on %s:%d",
                          self._host, self._port)
        while self.running:
            # noinspection PyBroadException
            try:
                (client_socket, address) = self._server_socket.accept()
            except socket.timeout:
                continue
            except:
                self._logger.exception("Critical error occurred, server "
                                       "stopped. Retry in 5 seconds.")
                time.sleep(5)
                continue
            else:
                if not self.running:
                    try:
                        client_socket.shutdown(socket.SHUT_RDWR)
                        client_socket.close()
                    except OSError:
                        self._logger.exception(
                            "Error occurred while closing connection"
                        )
                    break
            self._logger.info("Received connection from %s", address)
            client_thread = threading.Thread(
                target=self._serve_client,
                args=(client_socket,)
            )
            client_thread.start()
        self._server_socket.close()
        self._logger.info("Server socket closed.")

    @property
    def running(self):
        return self._running

    # noinspection PyBroadException
    def _serve_client(self, conn):
        """
        Processes client connection and retrieves messages from it.
        This function runs in a parallel thread to the server socket.
        :param conn: client socket handler
        :type conn: socket.socket
        """
        conn.settimeout(5)
        try:
            head = conn.recv(8)
            self._logger.debug("Received header: %s", head.decode())
            if head == self.HEAD_NEW_TASK:
                self._new_task_request(conn)
            elif head == self.HEAD_JOB_STATUS:
                self._job_status_request(conn)
            elif head == self.HEAD_JOB_RESULT:
                self._job_result_request(conn)
            elif head == self.HEAD_PING:
                conn.send(self.STATUS_OK)
            else:
                self._logger.warning("Invalid header: \"%s\".", head.decode())
        except socket.timeout:
            self._logger.exception("Client socket timed out.")
        except OSError:
            self._logger.exception("Connection error.")
        except json.JSONDecodeError:
            self._logger.exception("Received JSON is invalid.")
        except:
            self._logger.exception("Critical error.")
        finally:
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()

    def _new_task_request(self, conn):
        """
        Receives a new task from the client and spawns a new job.
        :param conn: client socket handler
        :raise ConnectionResetError
        :raise AssertionError
        """
        try:
            # FIXME error status is not sent on connection error
            data = recv_json(conn)
        except json.JSONDecodeError:
            conn.send(self.STATUS_ERROR)
            raise
        # REVIEW raise KeyError (or JsonError) instead of assertion.
        try:
            assert 'service' in data, "Service not specified."
            assert 'options' in data, "Options not specified."
        except AssertionError:
            conn.send(self.STATUS_ERROR)
            raise KeyError
        conn.send(self.STATUS_OK)
        command_cls = self.command_factory.get_command_class(data['service'])
        command = command_cls(data['options'])
        job = Job(command)
        self._logger.info("Created job %s", job)
        if send_json(conn, {'jobId': job.id}) == 0:
            raise ConnectionResetError("Connection reset by peer.")
        self._add_job(job)

    def _job_status_request(self, conn):
        """
        :param conn: client socket handler
        :raise ConnectionResetError
        """
        try:
            data = recv_json(conn)
        except json.JSONDecodeError:
            conn.send(self.STATUS_ERROR)
            raise
        assert 'jobId' in data
        job = self._get_job(data['jobId'])
        if job is None:
            conn.send(self.STATUS_ERROR)
            raise KeyError(data['jobId'])
        conn.send(self.STATUS_OK)
        if send_json(conn, {'status': job.status}) == 0:
            raise ConnectionResetError("Connection reset by peer.")

    def _job_result_request(self, conn):
        try:
            data = recv_json(conn)
        except json.JSONDecodeError:
            conn.send(self.STATUS_ERROR)
            raise
        assert 'jobId' in data
        job = self._get_job(data['jobId'])
        if job is None:
            conn.send(self.STATUS_ERROR)
            raise KeyError(data['jobId'])
        conn.send(self.STATUS_OK)
        json_data = {
            'return_code': job.result.return_code,
            'stdout': job.result.stdout,
            'stderr': job.result.stderr,
            'files': job.result.files
        }
        if send_json(conn, json_data) == 0:
            raise ConnectionResetError("Connection reset by peer.")

    def shutdown(self):
        self._running = False
        self._logger.debug("Poking server to stop.")
        socket.socket().connect((self._host, self._port))

    @staticmethod
    def check_connection(host=None, port=None):
        if host is None: host = pybioas.settings.QUEUE_HOST
        if port is None: port = pybioas.settings.QUEUE_PORT
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conn.connect((host, port))
            conn.send(QueueServer.HEAD_PING)
            response = conn.recv(8)
        except OSError:
            return False
        if response != QueueServer.STATUS_OK:
            return False
        else:
            return True


class Job:

    def __init__(self, runnable, args=None, kwargs=None):
        """
        Initialize a new job which executes start method of the runnable
        as a separate thread.
        :param runnable: runnable started by the worker
        :param args: arguments passed to the runnable's start method
        :param kwargs: keyword arguments passed to the runnable's start method
        """
        self._runnable = runnable
        self._id = uuid.uuid4().hex
        self.status = JobStatus.QUEUED
        self._args = args or ()
        self._kwargs = kwargs or {}
        self._result = None
        self.sig_finished = Signal()

    @property
    def id(self):
        return self._id

    def run(self):
        """
        Executes the target function and waits for completion.
        """
        self.status = JobStatus.RUNNING
        try:
            self._result = self._runnable.run(*self._args, **self._kwargs)
        except:
            self.status = JobStatus.FAILED
            raise
        else:
            self.status = JobStatus.COMPLETED
        finally:
            self.sig_finished(self.id)

    def kill(self):
        """
        Orders the running task to kill its process
        """
        self._runnable.kill()

    def suspend(self):
        """
        Tells the running task to suspend execution
        """
        self._runnable.suspend()

    def resume(self):
        """
        Tells the running task to resume suspended execution
        """
        self._runnable.resume()

    @property
    def result(self):
        """
        Returns job result if the job is finished, otherwise None
        :return: process output or None if not finished
        :rtype: ProcessOutput
        """
        if not self.is_finished():
            return None
        return self._result

    def is_finished(self):
        """
        Checks if the job is finished
        """
        return (self.status == JobStatus.COMPLETED or
                self.status == JobStatus.FAILED)

    def is_pending(self):
        """
        Checks if the job is pending execution
        """
        return self.status == JobStatus.QUEUED

    def is_running(self):
        """
        Checks if the job is already running
        """
        return self.status == JobStatus.RUNNING

    def __repr__(self):
        return "<Job> {id} - {status}".format(id=self.id, status=self.status)


class JobStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COLLECTED = "COLLECTED"
    FAILED = "FAILED"


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


# noinspection PyShadowingBuiltins
class ConnectionError(OSError):
    """ Connection error. """


# noinspection PyShadowingBuiltins
class ConnectionResetError(ConnectionError):
    """ Connection reset. """


class ServerError(Exception):
    """ Internal server error """


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
    client_socket.send(QueueServer.HEAD_NEW_TASK)

    send_json(client_socket, {
        "service": service,
        "options": values
    })
    status = client_socket.recv(8)
    if status != QueueServer.STATUS_OK:
        raise ServerError("something bad happened")
    data = recv_json(client_socket)
    job_id = data["jobId"]
    client_socket.shutdown(socket.SHUT_RDWR)
    client_socket.close()
    return DeferredResult(job_id, address)


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
        try:
            client_socket.send(QueueServer.HEAD_JOB_STATUS)
            send_json(client_socket, {"jobId": self.job_id})
            status = client_socket.recv(8)
            if status != QueueServer.STATUS_OK:
                raise ServerError("Internal server error")
            data = recv_json(client_socket)
        finally:
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
        try:
            client_socket.send(QueueServer.HEAD_JOB_RESULT)
            send_json(client_socket, {"jobId": self.job_id})
            status = client_socket.recv(8)
            if status != QueueServer.STATUS_OK:
                raise ServerError("Internal server error")
            data = recv_json(client_socket)
        finally:
            client_socket.close()
        # review: wrap data in an object like ProcessOutput
        return data

    def __repr__(self):
        return ("<DeferredResult {job_id} server={addr[0]}:{addr[1]}>"
                .format(job_id=self.job_id, addr=self.server_address))
