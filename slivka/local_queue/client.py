from collections import namedtuple

import zmq

zmq_ctx = zmq.Context()


class LocalQueueClient:
    JobStatusResponse = namedtuple("JobStatus", 'id, status, returncode')

    def __init__(self, address, protocol='tcp', secret=None):
        self.address = protocol + '://' + address
        self.secret = secret
        self.socket = zmq_ctx.socket(zmq.REQ)
        self.socket.connect(self.address)

    def submit_job(self, cmd, cwd, env):
        self.socket.send_json({
            'method': 'POST', 'cmd': cmd, 'cwd': cwd, 'env': env
        })
        response = self.socket.recv_json()
        if response.pop('ok'):
            return self.JobStatusResponse(**response)
        else:
            raise RequestError(response['error'])

    def get_job_status(self, id):
        self.socket.send_json({
            'method': 'GET', 'id': id
        })
        response = self.socket.recv_json()
        if response.pop('ok'):
            return self.JobStatusResponse(**response)
        else:
            raise RequestError(response['error'])


class RequestError(RuntimeError):
    pass
