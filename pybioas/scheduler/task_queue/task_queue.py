import itertools
import json
import queue
import socket
import threading
import time

from pybioas.scheduler.command.command_factory import CommandFactory
from pybioas.scheduler.task_queue.exceptions import ConnectionResetError
from pybioas.scheduler.task_queue.job import Job
from pybioas.scheduler.task_queue.utils import recv_json, send_json, get_logger

HOST = "localhost"
PORT = 9090


class TaskQueue:
    # Headers and status codes. Each is eight bytes long.
    HEAD_NEW_TASK = b'NEW TASK'
    HEAD_JOB_STATUS = b'JOB STAT'
    HEAD_JOB_RESULT = b'JOB RES '
    HEAD_PING = b'PING    '
    STATUS_OK = b'OK      '
    STATUS_ERROR = b'ERROR   '

    def __init__(self, host=HOST, port=PORT, num_workers=4):
        """
        :param host: server host address
        :param port: server port
        :param num_workers: number of concurrent workers to spawn
        """
        self._logger = get_logger()
        self._shutdown = False
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
        self._logger.debug('%s finished', self._jobs[job_id])


KILL_WORKER = 'KILL'


class Worker(threading.Thread):

    _counter = itertools.count(1)

    def __init__(self, jobs_queue):
        """
        :param jobs_queue: queue with the jobs to execute
        :type jobs_queue: queue.Queue[Job]
        """
        self._logger = get_logger()
        super(Worker, self).__init__(name="Worker-%d" % next(self._counter))
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

    HEAD_NEW_TASK = TaskQueue.HEAD_NEW_TASK
    HEAD_JOB_STATUS = TaskQueue.HEAD_JOB_STATUS
    HEAD_JOB_RESULT = TaskQueue.HEAD_JOB_RESULT
    HEAD_PING = TaskQueue.HEAD_PING
    STATUS_OK = TaskQueue.STATUS_OK
    STATUS_ERROR = TaskQueue.STATUS_ERROR

    def __init__(self, host, port, get_job, add_job):
        super(QueueServer, self).__init__(name='QueueServer')
        self._logger = get_logger()
        self._shutdown = False
        self._host = host
        self._port = port
        self._get_job = get_job
        self._add_job = add_job
        self._server_socket = None

    def run(self):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind((self._host, self._port))
        self._server_socket.settimeout(5)
        self._server_socket.listen(5)
        self._logger.info("Ready to accept connections on %s:%d",
                          self._host, self._port)
        while not self._shutdown:
            try:
                (client_socket, address) = self._server_socket.accept()
            except socket.timeout:
                continue
            else:
                if self._shutdown:
                    client_socket.shutdown(socket.SHUT_RDWR)
                    client_socket.close()
                    break
            self._logger.info("Received connection from %s", address)
            client_thread = threading.Thread(
                target=self._serve_client,
                args=(client_socket,)
            )
            client_thread.start()
        self._server_socket.close()
        self._logger.info("Server socket closed.")

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
                self._logger.warning("Invalid header: \"%s\"", head.decode())
        except socket.timeout:
            self._logger.exception("Client socket timed out")
        except OSError:
            self._logger.exception("Connection error")
        finally:
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()

    def _new_task_request(self, conn):
        """
        Receives a new task from the client and spawns a new job.
        :param conn: client socket handler
        :raise ConnectionResetError
        :raise KeyError
        """
        try:
            data = recv_json(conn)
        except json.JSONDecodeError:
            self._logger.error("Received invalid JSON form the client.")
            conn.send(self.STATUS_ERROR)
            return
        assert 'service' in data, "Service not specified."
        assert 'options' in data, "Options not specified."
        conn.send(self.STATUS_OK)
        command_cls = \
            CommandFactory.get_local_command_class(data['service'])
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
            return
        assert 'jobId' in data
        job = self._get_job(data['jobId'])
        if job is None:
            conn.send(self.STATUS_ERROR)
            return
        conn.send(self.STATUS_OK)
        if send_json(conn, {'status': job.status}) == 0:
            raise ConnectionResetError("Connection reset by peer.")

    def _job_result_request(self, conn):
        try:
            data = recv_json(conn)
        except json.JSONDecodeError:
            conn.send(self.STATUS_ERROR)
            return
        assert 'jobId' in data
        job = self._get_job(data['jobId'])
        if job is None:
            conn.send(self.STATUS_ERROR)
            return
        conn.send(self.STATUS_OK)
        if send_json(conn, job.result) == 0:
            raise ConnectionResetError("Connection reset by peer.")

    def shutdown(self):
        self._shutdown = True
        self._logger.debug("Poking server to stop.")
        socket.socket().connect((self._host, self._port))

    @staticmethod
    def check_connection(host=HOST, port=PORT):
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conn.connect((host, port))
            conn.send(TaskQueue.HEAD_PING)
            response = conn.recv(8)
        except OSError:
            return False
        if response != TaskQueue.STATUS_OK:
            return False
        else:
            return True
