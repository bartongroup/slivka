import logging
import pickle
import queue
import socket
import time
import threading

from .job import Job
from .utils import bytetonum, numtobyte


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s %(name)s %(levelname)s: %(message)s",
    "%d %b %H:%M:%S"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


HOST = 'localhost'
PORT = 9090


class Worker(object):

    MSG_NEW_TASK = b"NEW TASK"
    MSG_JOB_STATUS = b"JOB STAT"
    MSG_JOB_RESULT = b"JOB RES "
    STATUS_OK = b'OK  '

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
        print("Worker is ready to accept connections on {}:{}."
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
            logger.info("received connection from {}".format(address))
            client_thread = threading.Thread(
                target=self._handle_client,
                args=(client_socket,)
            )
            client_thread.start()
        self._server_socket.close()
        logger.info("socket closed.")

    def _handle_client(self, conn):
        """
        Processes client connection and retrieves messages from them.
        This function runs in a parallel thread to the server socket.
        :param conn: client socket handler
        """
        conn.settimeout(5)
        try:
            msg = conn.recv(8)
            logger.info("got message: {}".format(msg))
            if msg == Worker.MSG_NEW_TASK:
                self._new_task_request(conn)
            elif msg == Worker.MSG_JOB_STATUS:
                self._job_status_request(conn)
            elif msg == Worker.MSG_JOB_RESULT:
                self._job_result_request(conn)
        except socket.timeout:
            logger.warning("client socket timed out")
        except ConnectionAbortedError as e:
            logger.warning(str(e))
        finally:
            conn.close()
        logger.info("client handling done")

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
            raise ConnectionAbortedError("client did not respond.")
        try:
            runnable = pickle.loads(runnable_string)
        except pickle.PickleError:
            logger.error("serialized object is invalid")
            return
        if not conn.send(Worker.STATUS_OK):
            raise ConnectionAbortedError("connection aborted by the client")
        job = Job(runnable)
        logger.info("spawned job {}".format(job))
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
        logger.debug('{} finished'.format(self.jobs[job_id]))

    def process_queue(self):
        """
        A main loop where the worker scans the queue for tasks.
        """
        print("Worker is ready to process the queue.")
        while True:
            try:
                job = self._jobs_queue.get(timeout=5)
                logger.debug("picked {} from the queue".format(job))
                logger.debug("{} started".format(job))
                job.start()
            except queue.Empty:
                if self._shutdown:
                    break

    def shutdown(self):
        self._shutdown = True


def start_worker():
    worker = Worker()
    server_thread = threading.Thread(
        target=worker.listen,
        name="ServerThread"
    )
    queue_thread = threading.Thread(
        target=worker.process_queue,
        name="QueueThread"
    )
    queue_thread.start()
    server_thread.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("received shutdown signal")
        worker.shutdown()
    print("Waiting for threads to join.")
    server_thread.join()
    queue_thread.join()
