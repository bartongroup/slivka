import inspect
import io
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
from collections import namedtuple, deque
from select import select

import slivka
from slivka import JobStatus
from slivka.scheduler.exceptions import ServerError, JobNotFoundError

logger = logging.getLogger(__name__)


class TaskQueue:

    def __init__(self, host=None, port=None, num_workers=4):
        """
        :param host: server host address
        :param port: server port
        :param num_workers: number of concurrent workers to spawn
        """
        self._running = False
        if host is None or port is None:
            host, port = (
                slivka.settings.QUEUE_HOST, slivka.settings.QUEUE_PORT
            )
        self._queue = queue.Queue()
        self._jobs = dict()
        self._workers = [Worker(self._queue) for _ in range(num_workers)]
        self._server = QueueServer(
            host, port, self._jobs.get, self._enqueue_command
        )
        self._job_id_counter = itertools.count(1)

    def register_terminate_signal(self, *signals):
        for sig in signals:
            signal.signal(sig, self.terminate_signal_handler)

    def terminate_signal_handler(self, _signum, _frame):
        logger.warning("Termination signal received.")
        self.stop()

    def start(self, block=True):
        """Start the server thread and workers.

        Launches the task queue. Starts the server thread and all
        worker threads. Then, it waits for KeyboardInterrupt signal
        to call ``shutdown`` function and stop execution of the server and
        workers.
        If ``block`` parameter is set to False, queue will not block after
        starting server and workers and ``shutdown`` must be called manually
        from the main thread. This option is useful for interactive debugging
        and unit testing.

        :param block: block after starting (default: True)
        :type block: bool
        """
        self._running = True
        logger.info("Starting server.")
        self._server.start()
        logger.info("Starting %d workers.", len(self._workers))
        for worker in self._workers:
            worker.start()
        logger.info("Ready")
        if block:
            try:
                while self._running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Keyboard Interrupt; Shutting down...")
                self.stop()
            finally:
                self.shutdown()
                logger.info("Finished")

    def stop(self):
        """Stop the loop when running in the blocking mode."""
        self._running = False

    def shutdown(self):
        """Finish the work of the task queue.

        Puts kill worker signal for each alive worker to stop their threads and
        pokes the server with a dummy request to make it stop listening and
        return.

        This function should not be called manually unless using asynchronous
        interactive mode.
        """
        if self._running:
            raise RuntimeError("Can't shutdown while running.")
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
        """Add a new job to the queue.

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
        :type jobs_queue: queue.Queue[LocalCommand]
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
            except Exception:
                logger.exception("Failed to execute command.")
            finally:
                logger.info("%s completed %s", self.name, self._job)
                self._queue.task_done()
                self._job = None
        # noinspection PyUnreachableCode
        logger.debug("%s died.", self.name)


class QueueServer(threading.Thread):

    HEAD_NEW_TASK = b'NEW TASK'
    HEAD_JOB_STATUS = b'JOB STAT'
    HEAD_JOB_RESULT = b'JOB RESU'
    HEAD_PING = b'PING    '
    STATUS_OK = b'OK      '
    STATUS_ERROR = b'ERROR   '
    STATUS_NOT_FOUND = b'NOT FOUN'

    def __init__(self, host, port, get_job, add_job):
        """
        :param host: queue server host
        :param port: queue server port
        :param get_job: job getter function
        :type get_job: (int) -> LocalCommand
        :param add_job: job adder function
        :type add_job: (LocalCommand) -> int
        """
        super(QueueServer, self).__init__(name='QueueServer')
        self._running = False
        self._host, self._port = host, port
        self._get_job = get_job
        self._add_job = add_job
        self._server = None

    @property
    def running(self):
        """
        :return: if the queue server is running
        """
        return self._running

    def shutdown(self):
        """Stops the server."""
        self._running = False
        logger.debug("Poking server to stop.")
        dummy_conn = socket.socket()
        try:
            dummy_conn.connect((self._host, self._port))
        except ConnectionRefusedError:
            pass
        finally:
            dummy_conn.close()

    def run(self):
        """
        Runs a QueueServer thread which keeps listening on the socket to
        incoming connections and manages job submissions and status checking.
        When client is connected, a new thread is spawned to handle the
        request and produce response.
        """
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.bind((self._host, self._port))
        self._server.settimeout(0)
        self._server.listen(5)

        inputs, outputs = {self._server}, set()
        messages = dict()

        # noinspection PyShadowingNames
        def close_connection(sock):
            inputs.discard(sock)
            outputs.discard(sock)
            del messages[sock]
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()

        logger.info("Ready to accept connections on %s:%d",
                    self._host, self._port)
        self._running = True
        while self.running:
            readable, writable, exceptional = select(inputs, outputs, inputs)
            for sock in readable:  # type: socket.socket
                if sock is self._server:
                    conn, address = sock.accept()
                    conn.settimeout(0)
                    inputs.add(conn)
                    messages[conn] = deque()
                else:
                    try:
                        data = sock.recv(16)
                    except ConnectionResetError:
                        logger.exception('Connection reset')
                        data = None
                    if data:
                        head = data[:8]
                        content_length = int.from_bytes(data[8:16], 'big')
                        try:
                            request = self.read_json(
                                sock, content_length)
                        except json.JSONDecodeError:
                            logger.exception('Invalid json')
                            messages[sock].append(self.STATUS_ERROR)
                        except BlockingIOError:
                            logger.error('Not enough data to read from socket')
                            messages[sock].append(self.STATUS_ERROR)
                        else:
                            response = self.handle_request(head, request)
                            messages[sock].append(response)
                        outputs.add(sock)
                    else:
                        close_connection(sock)
            for sock in writable:  # type: socket.socket
                try:
                    msg = messages[sock].popleft()
                except (IndexError, KeyError):
                    outputs.discard(sock)
                else:
                    sock.sendall(msg)
            for sock in exceptional:  # type: socket.socket
                close_connection(sock)

        self._server.close()
        logger.info("Server socket closed.")

    @staticmethod
    def read_json(conn, length):
        """
        Reads json request of the given length from the client socket.
        Specified length must be available in the socket; otherwise function
        will raise BlockingIOError.

        :param conn: active client socket to read data from
        :param length: length of the json content
        :return: dictionary corresponding to received json
        :rtype: dict
        :raise json.JSONDecodeError:
        :raise BlockingIOError:
        """
        buffer = io.BytesIO()
        while length > 0:
            chunk = conn.recv(min(2048, length))
            length -= buffer.write(chunk)
        content = buffer.getvalue().decode('utf-8')
        if not content:
            return None
        else:
            return json.loads(content)

    def handle_request(self, header, request):
        try:
            if header == self.HEAD_NEW_TASK:
                response = self.submit_task_request(request)
            elif header == self.HEAD_JOB_STATUS:
                try:
                    response = self.job_status_request(request)
                except JobNotFoundError:
                    return self.STATUS_NOT_FOUND
            elif header == self.HEAD_JOB_RESULT:
                try:
                    response = self.job_result_request(request)
                except JobNotFoundError:
                    return self.STATUS_NOT_FOUND
            elif header == self.HEAD_PING:
                return self.STATUS_OK
            else:
                return self.STATUS_ERROR
        except KeyError:
            logger.exception('Invalid json request')
            return self.STATUS_ERROR
        else:
            return self.STATUS_OK + self.serialize_json(response)

    @staticmethod
    def serialize_json(obj):
        content = json.dumps(obj).encode('utf-8')
        content_length = len(content)
        length = content_length.to_bytes(8, 'big')
        return length + content

    def submit_task_request(self, request):
        command = LocalCommand(
            cmd=request['cmd'], cwd=request['cwd'], env=request['env']
        )
        logger.info("Created job %s", command)
        job_id = self._add_job(command)
        return {'jobId': job_id}

    def job_status_request(self, request):
        job = self._get_job(request['jobId'])
        if job is None:
            raise JobNotFoundError("Job %r not found" % request['jobId'])
        return {'status': job.status}

    def job_result_request(self, request):
        job = self._get_job(request['jobId'])
        if job is None:
            raise JobNotFoundError("Job %d not found" % request['jobId'])
        return {'return_code': job.return_code}

    @staticmethod
    def check_connection(address=None):
        """
        Tests if the queue server is running properly and accepting connections.

        :param address: address to connect to (defaults to (settings.QUEUE_HOST
         settings.QUEUE_PORT))
        :return: whether the server accepted connection properly
        """
        if address is None:
            address = (
                slivka.settings.QUEUE_HOST, slivka.settings.QUEUE_PORT
            )
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conn.connect(address)
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
    def submit_job(cmd, cwd, env=None, *, address=None):
        """
        Helper function which sends a new job to the local queue.
        It establishes the connection to the worker server and send new job
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
        :param address: local queue address
        :type address: (str, int)
        :return: id of the newly created job
        """
        status, data = QueueServer.communicate(
            QueueServer.HEAD_NEW_TASK,
            {'cmd': cmd, 'cwd': cwd, 'env': env or {}},
            address=address
        )
        try:
            return data['jobId']
        except KeyError:
            logger.critical(
                'Server responses with invalid json \n%s\n'
                'Expected "jobId" key',
                json.dumps(data, indent=2)
            )

    @staticmethod
    def get_job_status(job_id, *, address=None):
        """
        Helper function which requests the local queue for job status.
        It establishes the connection to the local queue server at specified
        host and port. If not given, it uses default local queue address from
        settings.
        :param job_id: job identifier received on submission
        :param address: local queue address
        :type address: (str, int)
        :return: job status string
        :raise JobNotFoundError
        :raise ServerError:
        """
        status, data = QueueServer.communicate(
            QueueServer.HEAD_JOB_STATUS,
            {'jobId': job_id},
            address=address
        )
        if status == QueueServer.STATUS_NOT_FOUND:
            raise JobNotFoundError
        elif status != QueueServer.STATUS_OK:
            raise ServerError('Internal server error')
        try:
            return data['status']
        except KeyError:
            logger.critical(
                'Server responded with invalid json \n%s\n'
                'Expected "status" key.',
                json.dumps(data, intent=2)
            )

    @staticmethod
    def get_job_return_code(job_id, *, address=None):
        """
        Helper function which requests the local queue for job output.
        It retrieves status code and console output from the process.
        :param job_id: job identifier received on submission
        :param address: local queue address
        :type address: (str, int)
        :return: output of the executed process
        :rtype: ProcessOutput
        """
        status, data = QueueServer.communicate(
            QueueServer.HEAD_JOB_RESULT,
            {'jobId': job_id},
            address=address
        )
        if status == QueueServer.STATUS_NOT_FOUND:
            raise JobNotFoundError
        elif status != QueueServer.STATUS_OK:
            logger.critical('Server encountered an error')
            raise ServerError('Internal server error')
        try:
            return data['return_code']
        except KeyError:
            logger.critical(
                'Server responded with invalid json \n%s\n'
                'Expected "return_code" key.',
                json.dumps(data, indent=2)
            )

    @staticmethod
    def communicate(head, content, *, address=None):
        if address is None:
            address = (
                slivka.settings.QUEUE_HOST,
                slivka.settings.QUEUE_PORT
            )
        content = QueueServer.serialize_json(content)
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conn.connect(address)
            conn.send(head + content)
            header = conn.recv(16)
            status = header[:8]
            content_length = int.from_bytes(header[8:], 'big')
            try:
                data = QueueServer.read_json(conn, content_length)
            except BlockingIOError:
                logger.critical('Invalid message length', exc_info=True)
                raise ServerError('Server did not send enough data')
            except json.JSONDecodeError:
                logger.critical('Invalid server response', exc_info=True)
                raise ServerError('Invalid server response')
            conn.shutdown(socket.SHUT_RDWR)
        finally:
            conn.close()
        return status, data


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
    :type _return_code: str
    """

    def __init__(self, cmd, cwd, env=None):
        self._cmd = cmd
        self._env = env
        self._cwd = cwd
        self._process = None
        self._status = JobStatus.QUEUED.value
        self._return_code = None

    def run(self):
        """
        Executes the command locally as a new subprocess.
        :return: output of the running process
        :rtype: ProcessOutput
        :raise FileNotFoundError: working dir from settings does not exist
        :raise OSError: error occurred when starting the process
        """
        logger.debug(
            "Starting local command cmd=%r env=%r cwd=%s",
            self._cmd, self._env, self._cwd
        )
        stdout = open(os.path.join(self._cwd, 'stdout.txt'), 'wb')
        stderr = open(os.path.join(self._cwd, 'stderr.txt'), 'wb')
        try:
            self._process = subprocess.Popen(
                self._cmd,
                stdout=stdout,
                stderr=stderr,
                env=dict(os.environ, **self._env),
                cwd=self._cwd
            )
            self._status = JobStatus.RUNNING.value
            self._process.wait()
        except Exception:
            self._status = JobStatus.FAILED.value
            raise
        else:
            self._return_code = self._process.returncode
            self._status = JobStatus.COMPLETED.value
        finally:
            stdout.close()
            stderr.close()
        return self._return_code

    @property
    def status(self):
        return self._status

    @property
    def return_code(self):
        """
        :rtype: str
        """
        return self._return_code

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
        return JobStatus(self._status).is_finished()

    def __repr__(self):
        return "<{0}>".format(self.__class__.__name__)


ProcessOutput = namedtuple('ProcessOutput', 'return_code, stdout, stderr')
