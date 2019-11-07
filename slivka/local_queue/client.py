import atexit
from collections import namedtuple

import zmq

zmq_ctx = zmq.Context()
atexit.register(zmq_ctx.destroy, 0)


class LocalQueueClient:
    JobStatusResponse = namedtuple("JobStatus", 'id, status, returncode')

    def __init__(self, address, protocol='tcp', secret=None):
        self.address = protocol + '://' + address
        self.secret = secret
        self.socket = zmq_ctx.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, 100)
        self.socket.setsockopt(zmq.REQ_RELAXED, 1)
        self.socket.connect(self.address)

    def submit_job(self, cmd, cwd, env):
        self.socket.send_json({
            'method': 'POST', 'cmd': cmd, 'cwd': cwd, 'env': env
        })
        try:
            response = self.socket.recv_json()
        except zmq.error.Again as e:
            raise ConnectionError("Could not connect to %s." % self.address) from None
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
