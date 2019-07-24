import io
import json
from collections import namedtuple
from hashlib import sha512
from socket import socket, SHUT_WR, AF_INET, AF_UNIX


class LocalQueueClient:
    JobStatusResponse = namedtuple("JobStatus", 'id, status, returncode')

    def __init__(self, address, secret=None):
        self.address = address
        self.secret = secret

    def submit_job(self, cmd, cwd, env):
        request = self._prepare_request(
            'POST', {'cmd': cmd, 'cwd': cwd, 'env': env}
        )
        return self.JobStatusResponse(
            **self._json_response(self._communicate(request))
        )

    def get_job_status(self, id):
        request = self._prepare_request('GET', {'id': id})
        return self.JobStatusResponse(
            **self._json_response(self._communicate(request))
        )

    def _json_response(self, response):
        status = response.readline().rstrip(b'\n\r')
        if status == b'OK':
            while response.readline().rstrip(b'\n\r'):
                pass
            content = response.read().decode()
            return json.loads(content)
        else:
            raise RequestError(status)

    def _prepare_request(self, method, json_content):
        content = json.dumps(json_content).encode()
        request = bytearray(b'%s\n' % method.encode())
        request += b'Content-Length: %d\n' % len(content)
        if self.secret:
            m = sha512()
            m.update(content)
            m.update(self.secret)
            request += b'Signature: %s\n' % m.hexdigest().encode()
        request += b'\n'
        request += content
        return request

    def _communicate(self, request):
        sock = socket(AF_INET if isinstance(self.address, tuple) else AF_UNIX)
        sock.settimeout(5)
        sock.connect(self.address)
        sock.sendall(request)
        sock.shutdown(SHUT_WR)
        buffer = bytearray()
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buffer += chunk
        sock.close()
        return io.BytesIO(buffer)


class RequestError(RuntimeError):
    pass
