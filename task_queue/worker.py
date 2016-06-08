import pickle
import queue
import socket
import threading

from .deferred_result import DeferredResult
from .job import Job
from .runnable_task import RunnableTask
from .utils import bytetonum, numtobyte, WorkerMsg


HOST = 'localhost'
PORT = 9090


class Worker(object):

    def __init__(self, host=HOST, port=PORT):
        self._queued_jobs = queue.Queue()
        self._running_jobs = set()
        self._completed_jobs = set()
        self.host, self.port = host, port
        self._server_socket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_STREAM
        )
        self._server_socket.bind((host, port))
        self._server_socket.setblocking(True)
        self._server_socket.listen(5)

    def listen(self):
        """
        Listens to incoming connections and starts a client thread.
        :return:
        """
        print("Worker is ready to accept connections on {}:{}"
              .format(self.host, self.port))
        try:
            while True:
                (client_socket, address) = self._server_socket.accept()
                print("Received connection from {}".format(address))
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,)
                )
                client_thread.start()
        except KeyboardInterrupt:
            print("Shutting down the worker socket.")
        finally:
            self._server_socket.shutdown(socket.SHUT_RDWR)
            self._server_socket.close()
            print("Socket closed.")

    def _handle_client(self, conn):
        """
        Processes client connection and retrieves task from them
        :param conn: client socket handler
        """
        conn.settimeout(5)
        try:
            msg_length = bytetonum(conn.recv(4))
            runnable_string = conn.recv(msg_length)
        except socket.timeout:
            conn.close()
            print("Client did not respond.")
            return
        runnable = pickle.loads(runnable_string)
        if not conn.send(WorkerMsg.STATUS_OK):
            conn.close()
            print("Connection aborted by the client")
        else:
            job = Job(runnable)
            print("Spawned job {}".format(job))
            conn.send(job.id.encode())
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()
            self._queue_job(job)
        print("Client handling done")

    def _queue_job(self, job):
        pass

    def _on_job_finished(self, job_id):
        pass


def queue_run(runnable):
    """
    Sends the task to the worker which enqueues it a new job.
    :param runnable: runnable task instance to be scheduled
    :return: DeferredResult associated with the job
    """
    if not isinstance(runnable, RunnableTask):
        raise TypeError("Runnable must implement RunnableTask")
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))

    runnable_string = pickle.dumps(runnable)

    client_socket.send(numtobyte(len(runnable_string), 4))
    client_socket.send(runnable_string)
    status_code = client_socket.recv(4)
    if status_code != WorkerMsg.STATUS_OK:
        raise ConnectionError("Worker returned status code: {}"
                              .format(status_code))
    job_id = client_socket.recv(32).decode()
    client_socket.shutdown(socket.SHUT_RDWR)
    client_socket.close()

    return DeferredResult(job_id, (HOST, PORT))
