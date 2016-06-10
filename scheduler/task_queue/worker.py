import pickle
import queue
import socket
import time
import threading

from .deferred_result import DeferredResult
from .job import Job
from .runnable_task import RunnableTask
from .utils import bytetonum, numtobyte, WorkerMsg


HOST = 'localhost'
PORT = 9090


class Worker(object):

    def __init__(self, host=HOST, port=PORT):
        self._shutdown = False
        self._jobs_queue = queue.Queue()
        self.jobs = dict()
        self.host, self.port = host, port
        self._server_socket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_STREAM
        )
        self._server_socket.bind((host, port))
        self._server_socket.settimeout(5)
        self._server_socket.listen(5)

    def listen(self):
        """
        Listens to incoming connections and starts a client thread.
        :return:
        """
        print("Worker is ready to accept connections on {}:{}"
              .format(self.host, self.port))
        while True:
            try:
                (client_socket, address) = self._server_socket.accept()
            except socket.timeout:
                continue
            else:
                if self._shutdown:
                    client_socket.close()
            finally:
                if self._shutdown:
                    break
            print("Received connection from {}".format(address))
            client_thread = threading.Thread(
                target=self._handle_client,
                args=(client_socket,)
            )
            client_thread.start()
        self._server_socket.close()
        print("Socket closed.")

    def _handle_client(self, conn):
        """
        Processes client connection and retrieves task from them
        :param conn: client socket handler
        """
        conn.settimeout(5)
        try:
            msg = conn.recv(8)
            print("msg: {}".format(msg))
        except socket.timeout:
            return
        if msg == WorkerMsg.MSG_NEW_TASK:
            self._new_task_request(conn)
        elif msg == WorkerMsg.MSG_JOB_STATUS:
            self._job_status_request(conn)
        elif msg == WorkerMsg.MSG_JOB_RESULT:
            self._job_result_request(conn)
        print("Client handling done")

    def _new_task_request(self, conn):
        """
        Receives a new task from the client and spawns a new job
        :param conn: client socket handler
        :raise ConnectionAbortedError
        :raise pickle.UnpicklingError
        """
        try:
            msg_length = bytetonum(conn.recv(4))
            runnable_string = conn.recv(msg_length)
        except socket.timeout:
            conn.close()
            raise ConnectionAbortedError("Client did not respond.")
        runnable = pickle.loads(runnable_string)
        if not conn.send(WorkerMsg.STATUS_OK):
            conn.close()
            raise ConnectionAbortedError("Connection aborted by the client")
        job = Job(runnable)
        print("Spawned job {}".format(job))
        conn.send(job.id.encode())
        conn.shutdown(socket.SHUT_RDWR)
        conn.close()
        self._queue_job(job)

    def _queue_job(self, job):
        """
        Adds a new job to the queue.
        :param job: new job
        """
        job.sig_finished.register(self._on_job_finished)
        self.jobs[job.id] = job
        self._jobs_queue.put(job)

    def _job_status_request(self, conn):
        """
        Handles job status request from the client.
        Receives job id from the socket and sends back the status of the job
        :param conn: client socket handler
        """
        job_id = conn.recv(32).decode()
        status = self.jobs[job_id].status
        conn.send(status.encode())
        conn.shutdown(socket.SHUT_RDWR)
        conn.close()

    def _job_result_request(self, conn):
        """
        Handles job result request from the client.
        Exchanges job if for the serialised JobResult fetched from the job.
        :param conn: client socket handler
        """
        job_id = conn.recv(32).decode()
        result = self.jobs[job_id].result
        result_bytes = pickle.dumps(result)
        conn.send(numtobyte(len(result_bytes), 4))
        conn.send(result_bytes)
        conn.shutdown(socket.SHUT_RDWR)
        conn.close()

    def _on_job_finished(self, job_id):
        """
        Callback slot activated when the job is finished.
        :param job_id: id of the job which sent the signal
        """
        print('{} finished'.format(self.jobs[job_id]))

    def process_queue(self):
        """
        A main loop where the worker scans the queue for tasks.
        """
        print("Worker is ready to process the queue.")
        while True:
            try:
                job = self._jobs_queue.get(timeout=5)
                print("Retrieved {} from the queue".format(job))
                job.start()
                print("{} started".format(job))
            except queue.Empty:
                if self._shutdown:
                    break

    def shutdown(self):
        self._shutdown = True


def start_worker():
    worker = Worker()
    server_thread = threading.Thread(target=worker.listen)
    server_thread.start()
    queue_thread = threading.Thread(target=worker.process_queue)
    queue_thread.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        worker.shutdown()
    server_thread.join()
    queue_thread.join()


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
    client_socket.send(WorkerMsg.MSG_NEW_TASK)

    runnable_string = pickle.dumps(runnable)

    client_socket.send(numtobyte(len(runnable_string), 4))
    client_socket.send(runnable_string)
    status_code = client_socket.recv(4)
    if status_code != WorkerMsg.STATUS_OK:
        raise ConnectionError("Worker returned code: {0}"
                              .format(status_code.decode()))
    job_id = client_socket.recv(32).decode()
    client_socket.shutdown(socket.SHUT_RDWR)
    client_socket.close()

    return DeferredResult(job_id, (HOST, PORT))
