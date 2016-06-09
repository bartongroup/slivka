import pickle
import socket

from .utils import WorkerMsg, bytetonum


class DeferredResult:

    def __init__(self, job_id, server_address):
        self.job_id = job_id
        self.server_address = server_address

    @property
    def status(self):
        """
        Asks the server for the status of the job linked to this deferred
        result instance.
        :return: current job status
        :rtype: job.JobStatus
        """
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(self.server_address)
        client_socket.send(WorkerMsg.MSG_JOB_STATUS)

        client_socket.send(self.job_id.encode())
        job_status = client_socket.recv(16).decode()
        client_socket.shutdown(socket.SHUT_RDWR)
        client_socket.close()
        return job_status

    @property
    def result(self):
        """
        Asks the server for the result of the job associated with this
        deferred result.
        :return: job result or None if not finished
        :rtype: job.JobResult
        """
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(self.server_address)
        client_socket.send(WorkerMsg.MSG_JOB_RESULT)

        client_socket.send(self.job_id.encode())
        msg_length = bytetonum(client_socket.recv(4))
        job_result = client_socket.recv(msg_length)
        client_socket.shutdown(socket.SHUT_RDWR)
        client_socket.close()
        return pickle.loads(job_result)

    def __repr__(self):
        return ("<DeferredResult> {job_id} server: {addr[0]}:{addr[1]}"
                .format(job_id=self.job_id, addr=self.server_address))
