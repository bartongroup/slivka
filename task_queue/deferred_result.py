from socket import socket, AF_INET, SOCK_STREAM

from task_queue.worker import HOST, PORT, WorkerMsg


class DeferredResult:

    def __init__(self, job_id, server_address=(HOST, PORT)):
        self.job_id = job_id
        self.server_address = server_address

    @property
    def status(self):
        client_socket = socket(AF_INET, SOCK_STREAM)
        client_socket.connect(self.server_address)
        client_socket.send(WorkerMsg.GET_JOB_STATUS)
        job_status = client_socket.recv(16)
        client_socket.close()
        return job_status

    @property
    def result(self):
        client_socket = socket(AF_INET, SOCK_STREAM)
        client_socket.connect(self.server_address)
        client_socket.send(WorkerMsg.GET_JOB_RESULT)
        job_result = client_socket.recv(4096)
        client_socket.close()
        return job_result
