import asyncio
import enum
import logging
import os
import re
from hashlib import sha512
from uuid import uuid4

import simplejson as json


log = logging.getLogger('slivka-queue')


class Status(enum.Enum):
    QUEUED = 0
    RUNNING = 1
    COMPLETED = 2
    INTERRUPTED = 3
    FAILED = 4
    ERROR = 5
    UNDEFINED = -1


class ShellCommandWrapper:
    def __init__(self, cmd, cwd, env=None):
        self.id = uuid4().int
        self.cmd = cmd
        self.cwd = cwd
        self.env = env or {}

    def __repr__(self):
        return "Command(id={}, cmd={}, cwd={})".format(self.id, self.cmd, self.cwd)


class ProcessStatus:
    def __init__(self):
        self.status = Status.QUEUED
        self.return_code = None


class LocalQueue:
    def __init__(self, address, workers=1, secret=None):
        self.address = address
        self.num_workers = workers
        self.secret = secret
        if not secret:
            log.warning('No secret used.')
        self.server = None
        self.queue = asyncio.Queue()
        self.workers = []
        self.stats = {}

    def start_workers(self, loop=None):
        if self.workers:
            raise RuntimeError("Workers are already running")
        loop = loop or asyncio.get_event_loop()
        for _ in range(self.num_workers):
            self.workers.append(loop.create_task(self._worker(self.queue)))

    async def _worker(self, queue):
        log.info("Worker spawned")
        while True:
            log.debug('Waiting for next command')
            command = await queue.get()  # type: ShellCommandWrapper
            log.info('Starting %r', command)
            stdout = open(os.path.join(command.cwd, 'stdout.txt'), 'wb')
            stderr = open(os.path.join(command.cwd, 'stderr.txt'), 'wb')
            proc = await asyncio.create_subprocess_shell(
                command.cmd,
                stdout=stdout, stderr=stderr,
                cwd=command.cwd, env=dict(os.environ, **command.env)
            )
            self.stats[command.id].status = Status.RUNNING
            try:
                return_code = await proc.wait()
                self.stats[command.id].return_code = return_code
                self.stats[command.id].status = (
                    Status.COMPLETED if return_code == 0 else Status.FAILED
                )
                log.info('%r completed with status %d', command, return_code)
            except asyncio.CancelledError:
                log.info('Tearing down')
                proc.terminate()
                self.stats[command.id].return_code = await proc.wait()
                self.stats[command.id].status = Status.INTERRUPTED
                break
            finally:
                try:
                    proc.kill()
                except OSError:
                    pass
                stdout.close()
                stderr.close()
        log.info("Worker terminated")

    class HeaderError(ValueError):
        pass

    class MethodError(ValueError):
        pass

    class DigestError(ValueError):
        pass

    async def handle_connection(self, reader, writer):
        """
        :type reader: asyncio.StreamReader
        :type writer: asyncio.StreamWriter
        """
        try:
            method, headers, content = await self._process_incoming_data(reader)
            if method == b'GET':
                response = self.do_GET(headers, content)
            elif method == b'POST':
                response = self.do_POST(headers, content)
            else:
                raise self.MethodError(method)
        except self.MethodError:
            log.exception('Method error')
            writer.write(b'METHOD ERROR')
        except self.HeaderError:
            log.exception('Header error')
            writer.write(b'HEADER ERROR')
        except asyncio.TimeoutError:
            log.exception('Timeout error')
            writer.write(b'TIMEOUT ERROR')
        except self.DigestError:
            log.exception('Signature error')
            writer.write(b'SIGNATURE ERROR')
        except (json.JSONDecodeError, KeyError):
            log.exception('JSON error')
            writer.write(b'JSON ERROR')
        else:
            writer.write(b'OK\nContent-Length: %d\n\n' % len(response))
            writer.write(json.dumps(response).encode())
        finally:
            await writer.drain()
            writer.close()

    async def _process_incoming_data(self, reader):
        method = (await reader.readline()).rstrip(b'\n\r')
        log.debug('Request method %s', method)
        if not (method == b'GET' or method == b'POST'):
            raise self.MethodError(method)
        try:
            headers = await asyncio.wait_for(LocalQueue._consume_headers(reader), 1)
            content_length = int(headers[b'Content-Length'])
        except (TimeoutError, ValueError, KeyError) as exc:
            raise self.HeaderError() from exc
        log.debug('Request headers %s', headers)
        raw_content = bytearray()
        while len(raw_content) < content_length:
            raw_content.extend(await asyncio.wait_for(reader.read(4096), 1))
        log.debug('request content %s', raw_content)
        if self.secret:
            signature = headers.get(b'Signature', b'')
            m = sha512()
            m.update(raw_content)
            m.update(self.secret)
            if m.hexdigest().encode() != signature:
                raise LocalQueue.DigestError()
        json_content = json.loads(raw_content.decode())
        return method, headers, json_content

    @staticmethod
    async def _consume_headers(reader):
        headers = {}
        while True:
            line = (await reader.readline()).rstrip(b'\n\r')
            if not line:
                break
            match = re.match(rb'([\w-]+): (.+)$', line)
            if match is None:
                raise LocalQueue.HeaderError('Line %s is not a valid header' % line)
            headers[match.group(1)] = match.group(2)
        return headers

    def do_GET(self, headers, content):
        status = self.stats.get(content['id'])
        if status is None:
            return {
                'id': content['id'],
                'status': Status.UNDEFINED.name,
                'returncode': None
            }
        else:
            return {
                'id': content['id'],
                'status': status.status.name,
                'returncode': status.return_code
            }

    def do_POST(self, headers, content):
        cmd = ShellCommandWrapper(
            cmd=content['cmd'],
            cwd=content['cwd'],
            env=content.get('env')
        )
        self.queue.put_nowait(cmd)
        self.stats[cmd.id] = ProcessStatus()
        log.info('Submitted %r', cmd)
        return {
            'id': cmd.id,
            'status': Status.QUEUED.name,
            'returncode': None
        }

    async def start_server(self):
        log.info('Starting the server')
        if isinstance(self.address, tuple):
            host, port = self.address
            self.server = await asyncio.start_server(self.handle_connection, host, port)
        elif isinstance(self.address, str):
            self.server = await asyncio.start_unix_server(self.handle_connection, self.address)
        else:
            raise ValueError("Invalid address %s" % self.address)
        log.info('Server is listening on %s', self.server.sockets[0].getsockname())

    def close(self):
        for worker in self.workers:
            worker.cancel()
        self.server.close()

    async def wait_closed(self):
        await self.server.wait_closed()
        await asyncio.gather(*self.workers, return_exceptions=True)

    def run(self, loop=None):
        loop = loop or asyncio.get_event_loop()
        self.start_workers(loop)
        loop.run_until_complete(self.start_server())
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                self.close()
                loop.run_until_complete(self.wait_closed())
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()
