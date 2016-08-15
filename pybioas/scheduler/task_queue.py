import inspect
import itertools
import json
import logging
import os
import queue
import signal
import socket
import subprocess
import threading
import time
import weakref
from collections import namedtuple

import pybioas
from pybioas.scheduler.exc import ConnectionResetError, ServerError
from . import recv_json, send_json

logger = logging.getLogger(__name__)


class TaskQueue:
    # Headers and status codes. Each is eight bytes long.

    def __init__(self, host=None, port=None, num_workers=4):
        """
        :param host: server host address
        :param port: server port
        :param num_workers: number of concurrent workers to spawn
        """
        if host is None or port is None:
            host, port = (
                pybioas.settings.QUEUE_HOST, pybioas.settings.QUEUE_PORT
            )
        self._queue = queue.Queue()
        self._jobs = dict()
        self._workers = [Worker(self._queue) for _ in range(num_workers)]
        self._server = QueueServer(
            host, port, self._jobs.get, self._enqueue_command
        )
        self._job_id_counter = itertools.count(1)

    def start(self, async=False):
        """
        Launches the task queue. Starts the server thread and starts all
        worker threads. Then it waits for KeyboardInterrupt signal
        to stop execution of the server and workers.
        Waits for all threads to join before exiting.
        """
        logger.info("Starting server.")
        self._server.start()
        logger.info("Starting workers.")
        for worker in self._workers:
            worker.start()
        if async:
            return
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.shutdown()

    def shutdown(self):
        """
        Flushes the task queue and puts kill worker signal for each
        alive worker.
        Then, pokes the server to stop listening and return.
        :return:
        """
        logger.debug("Shutdown signal.")

        logger.debug("Shutting down the server.")
        self._server.shutdown()

        num_workers = sum(worker.is_alive() for worker in self._workers)
        logger.debug("Sending %d KILLS to workers.", num_workers)
        with self._queue.mutex:
            self._queue.unfinished_tasks -= len(self._queue.queue)
            self._queue.queue.clear()
            self._queue.queue.extend([KILL_WORKER] * num_workers)
            self._queue.unfinished_tasks += num_workers
            self._queue.not_empty.notify_all()

        self._server.join()
        logger.debug("Server thread joined.")
        for worker in self._workers:
            worker.join()
        logger.debug("Workers joined.")

    def _enqueue_command(self, command):
        """
        Adds a new job to the queue.
        :param command: new command to execute
        :type command: LocalCommand
        :return: id of the job
        :rtype: int
        """
        job_id = next(self._job_id_counter)
        logger.debug("Adding job %s to queue.", command)
        self._jobs[job_id] = command
        self._queue.put(command)
        return job_id


KILL_WORKER = 'KILL'


class Worker(threading.Thread):

    _counter = itertools.count(1)

    def __init__(self, jobs_queue):
        """
        :param jobs_queue: queue with the jobs to execute
        :type jobs_queue: queue.Queue[Job]
        """
        super(Worker, self).__init__(name="Worker-%d" % next(self._counter))
        self._queue = jobs_queue
        self._job = None

    def run(self):
        """
        Runs Worker thread which polls queue for commands and starts them.
        """
        logger.debug("%s started.", self.name)
        while True:
            self._job = self._queue.get()
            logger.info("%s picked up %s", self.name, self._job)
            # noinspection PyBroadException
            try:
                if self._job == KILL_WORKER:
                    break
                else:
                    self._job.run()
            except:
                logger.exception("Failed to execute command.")
            finally:
                logger.info("%s completed %s", self.name, self._job)
                self._queue.task_done()
                self._job = None
        logger.debug("%s died.", self.name)


class QueueServer(threading.Thread):

    HEAD_NEW_TASK = b'NEW TASK'
    HEAD_JOB_STATUS = b'JOB STAT'
    HEAD_JOB_RESULT = b'JOB RES '
    HEAD_PING = b'PING    '
    STATUS_OK = b'OK      '
    STATUS_ERROR = b'ERROR   '

    def __init__(self, host, port, get_job, add_job):
        """
        :param host: queue server host
        :param port: queue server port
        :param get_job: job getter function
        :type get_job: (dict, int) -> LocalCommand
        :param add_job: job adder function
        :type add_job: (TaskQueue, LocalCommand) -> int
        """
        super(QueueServer, self).__init__(name='QueueServer')
        self._running = True
        self._host, self._port = host, port
        self._get_job = get_job
        self._add_job = add_job
        self._server_socket = None

    def run(self):
        """
        Runs a QueueServer thread which keeps listening on the socket to
        incoming connections and manages job submissions and status checking.
        When client is connected, a new thread is spawned to handle the
        request and produce response.
        :return:
        """
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind((self._host, self._port))
        self._server_socket.settimeout(5)
        self._server_socket.listen(5)
        logger.info("Ready to accept connections on %s:%d",
                    self._host, self._port)
        while self.running:
            # noinspection PyBroadException
            try:
                (client_socket, address) = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                logger.exception("Critical error occurred, server "
                                 "stopped. Retry in 5 seconds.")
                time.sleep(5)
                continue
            else:
                if not self.running:
                    try:
                        client_socket.shutdown(socket.SHUT_RDWR)
                        client_socket.close()
                    except OSError:
                        logger.exception(
                            "Error occurred while closing connection"
                        )
                    break
            logger.info("Received connection from %s", address)
            client_thread = threading.Thread(
                target=self._serve_client,
                args=(client_socket,)
            )
            client_thread.start()
        self._server_socket.close()
        logger.info("Server socket closed.")

    @property
    def running(self):
        """
        :return: if the queue server is running
        """
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
            logger.debug("Received header: %s", head.decode())
            if head == self.HEAD_NEW_TASK:
                self._new_task_request(conn)
            elif head == self.HEAD_JOB_STATUS:
                self._job_status_request(conn)
            elif head == self.HEAD_JOB_RESULT:
                self._job_result_request(conn)
            elif head == self.HEAD_PING:
                conn.send(self.STATUS_OK)
            else:
                logger.warning("Invalid header: \"%s\".", head.decode())
        except socket.timeout:
            logger.exception("Client socket timed out.")
        except OSError:
            logger.exception("Connection error.")
        except json.JSONDecodeError:
            logger.exception("Received JSON is invalid.")
        except:
            logger.exception("Critical error.")
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
            data = recv_json(conn)
        except json.JSONDecodeError:
            conn.send(self.STATUS_ERROR)
            raise
        conn.send(self.STATUS_OK)
        command = LocalCommand(cmd=data['cmd'], cwd=data['cwd'],
                               env=data['env'])
        logger.info("Created job %s", command)
        job_id = self._add_job(command)
        if send_json(conn, {'jobId': job_id}) == 0:
            raise ConnectionResetError("Connection reset by peer.")

    def _job_status_request(self, conn):
        """
        Handles status request and sends job status to the client.
        :param conn: client socket handler
        :raise KeyError: Job with given key does not exist
        :raise ConnectionResetError: Connection to client lost
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
        """
        Handles job result request and sends back the job result.
        :param conn: client socket handler
        :raise: KeyError: Job with given id doesn't exist
        :raise ConnectionResetError: Connection to client lost
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
        json_data = {
            'return_code': job.output.return_code,
            'stdout': job.output.stdout,
            'stderr': job.output.stderr
        }
        if send_json(conn, json_data) == 0:
            raise ConnectionResetError("Connection reset by peer.")

    def shutdown(self):
        """
        Stops the server.
        """
        self._running = False
        logger.debug("Poking server to stop.")
        socket.socket().connect((self._host, self._port))

    @staticmethod
    def check_connection(host=None, port=None):
        """
        Tests if the queue server is running properly and accepting connections.
        :param host: host to connect to (defaults to settings.QUEUE_HOST)
        :param port: port to connect to (defaults to settings.QUEUE_PORT)
        :return: whether the server accepted connection properly
        """
        if host is None or port is None:
            (host, port) = (
                pybioas.settings.QUEUE_HOST, pybioas.settings.QUEUE_PORT
            )
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conn.connect((host, port))
            conn.send(QueueServer.HEAD_PING)
            response = conn.recv(8)
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            return False
        finally:
            conn.close()
        if response == QueueServer.STATUS_OK:
            return True
        else:
            return False

    @staticmethod
    def submit_job(cmd, cwd, env=None, *, host=None, port=None):
        """
        Helper function which sends a new job to the local queue.
        It esablishes the connection to the worker server and send new job
        details. You need to specify list of command arguments, working
        directory and, optionally, environment variables.
        By default, it connect to the queue address specified in the settings,
        but you can override it specifying `host` and `port` arguments.
        :param cmd: list of command line arguments to execute
        :type cmd: list[str]
        :param cwd: absolute path of current working directory for the command
        :type cwd: str
        :param env: environment variables
        :type env: dict[str, str]
        :param host: queue server host address (typically localhost)
        :param port: queue server listening port
        :return: id of the newly created job
        """
        if host is None or port is None:
            (host, port) = (
                pybioas.settings.QUEUE_HOST, pybioas.settings.QUEUE_PORT
            )
        logger.debug(
            "Submitting new command\ncmd: %r\nenv: %r\ncwd: %s", cmd, env, cwd
        )
        json_data = {'cmd': cmd, 'cwd': cwd, 'env': env or {}}
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conn.connect((host, port))
            conn.send(QueueServer.HEAD_NEW_TASK)
            send_json(conn, json_data)
            status = conn.recv(8)
            if status != QueueServer.STATUS_OK:
                raise ServerError('Internal server error')
            data = recv_json(conn)
            job_id = data['jobId']
            conn.shutdown(socket.SHUT_RDWR)
        finally:
            conn.close()
        return job_id

    @staticmethod
    def get_job_status(job_id, *, host=None, port=None):
        """
        Helper function which requests the local queue for job status.
        It establishes the connection to the local queue server at specified
        host and port. If not given, it uses default local queue address from
        settings.
        :param job_id: job identifier received on submission
        :param host: local queue host address (typically localhost)
        :param port: local queue listening port
        :return: job status string
        """
        if host is None or port is None:
            (host, port) = (
                pybioas.settings.QUEUE_HOST, pybioas.settings.QUEUE_PORT
            )
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conn.connect((host, port))
            conn.send(QueueServer.HEAD_JOB_STATUS)
            send_json(conn, {'jobId': job_id})
            status = conn.recv(8)
            if status != QueueServer.STATUS_OK:
                raise ServerError('Internal server error')
            data = recv_json(conn)
            conn.shutdown(socket.SHUT_RDWR)
        finally:
            conn.close()
        return data['status']

    @staticmethod
    def get_job_output(job_id, *, host=None, port=None):
        """
        Helper function which requests the local queue for job output.
        It retrieves status code and console output from the process.
        :param job_id: job identifier received on submission
        :param host: local queue host address (typically localhost)
        :param port: local queue port
        :return: output of the executed process
        :rtype: ProcessOutput
        """
        if host is None or port is None:
            (host, port) = (
                pybioas.settings.QUEUE_HOST, pybioas.settings.QUEUE_PORT
            )
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conn.connect((host, port))
            conn.send(QueueServer.HEAD_JOB_RESULT)
            send_json(conn, {'jobId': job_id})
            status = conn.recv(8)
            if status != QueueServer.STATUS_OK:
                raise ServerError('Internal server error')
            data = recv_json(conn)
        finally:
            conn.close()
        return ProcessOutput(**data)


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


class LocalCommand:
    """
    Class used for a local command execution.
    :type _cmd: list[str]
    :type _env: dict[str, str]
    :type _cwd: str
    :type _process: subprocess.Popen
    :type _status: str
    :type _output: ProcessOutput
    """
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_EXCEPTION = 'exception'
    STATUS_SUCCESS = 'success'

    def __init__(self, cmd, cwd, env=None):
        self._cmd = cmd
        self._env = env
        self._cwd = cwd
        self._process = None
        self._status = self.STATUS_QUEUED
        self._output = None

    def run(self):
        """
        Executes the command locally as a new subprocess.
        :return: output of the running process
        :rtype: ProcessOutput
        :raise FileNotFoundError: working dir from settings does not exist
        :raise OSError: error occurred when starting the process
        """
        self._status = self.STATUS_RUNNING
        logger.debug(
            "Starting local command cmd=%r env=%r cwd=%s",
            self._cmd, self._env, self._cwd
        )
        try:
            self._process = subprocess.Popen(
                self._cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=dict(os.environ, **self._env),
                cwd=self._cwd
            )
            stdout, stderr = self._process.communicate()
            return_code = self._process.returncode
        except:
            self._status = self.STATUS_EXCEPTION
            raise
        else:
            self._status = self.STATUS_SUCCESS
        self._output = ProcessOutput(
            return_code,
            stdout.decode(),
            stderr.decode()
        )
        return self._output

    @property
    def status(self):
        return self._status

    @property
    def output(self):
        """
        :rtype: ProcessOutput
        """
        return self._output

    def terminate(self):
        """
        :raises OSError: no such process
        """
        self._process.terminate()

    def kill(self):
        """
        :raises OSError: no such process
        """
        self._process.kill()

    def suspend(self):
        try:
            # noinspection PyUnresolvedReferences
            self._process.send_signal(signal.SIGSTOP)
        except AttributeError:
            logger.warning(
                'SIGSTOP is not available on this platform'
            )

    def resume(self):
        try:
            # noinspection PyUnresolvedReferences
            self._process.send_signal(signal.SIGCONT)
        except AttributeError:
            logger.warning(
                'SIGCONT is not available on this platform'
            )

    def is_finished(self):
        return (self._status == self.STATUS_SUCCESS or
                self._status == self.STATUS_EXCEPTION)

    def __repr__(self):
        return "<{0}>".format(self.__class__.__name__)


ProcessOutput = namedtuple('ProcessOutput', 'return_code, stdout, stderr')
