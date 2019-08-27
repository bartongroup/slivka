import asyncio
import itertools
import logging
import os
import time

import zmq
import zmq.asyncio as aiozmq

from slivka import JobStatus

log = logging.getLogger('slivka-queue')


try:
    get_running_loop = asyncio.get_running_loop
except AttributeError:
    get_running_loop = asyncio.get_event_loop


class ShellCommandWrapper:
    counter = itertools.count(1)

    def __init__(self, cmd, cwd, env=None):
        self.id = int(time.time()) << 32 | next(self.counter) & 0xffffffff
        self.cmd = cmd
        self.cwd = cwd
        self.env = env or {}
        self.env.setdefault('PATH', os.getenv('PATH'))

    def __repr__(self):
        return "Command(id={}, cmd={}, cwd={})".format(self.id, self.cmd, self.cwd)


class ProcessStatus:
    def __init__(self):
        self.status = JobStatus.QUEUED
        self.return_code = None


class LocalQueue:
    zmq_ctx = aiozmq.Context()

    def __init__(self, address, protocol='tcp', workers=1, secret=None):
        self.address = protocol + '://' + address
        self.num_workers = workers
        self.secret = secret
        if not secret:
            log.warning('No secret used.')
        self.server = None
        self.queue = asyncio.Queue()
        self.workers = []
        self.stats = {}

    async def _worker(self, queue):
        log.info("Worker spawned")
        while True:
            log.debug('Waiting for next command')
            command = await queue.get()  # type: ShellCommandWrapper
            log.info('Starting %r', command)
            stdout = open(os.path.join(command.cwd, 'stdout'), 'wb')
            stderr = open(os.path.join(command.cwd, 'stderr'), 'wb')
            proc = await asyncio.create_subprocess_shell(
                command.cmd,
                stdout=stdout,
                stderr=stderr,
                cwd=command.cwd,
                env=command.env
            )
            self.stats[command.id].status = JobStatus.RUNNING
            try:
                return_code = await proc.wait()
                self.stats[command.id].return_code = return_code
                self.stats[command.id].status = (
                    JobStatus.COMPLETED if return_code == 0 else JobStatus.FAILED
                )
                log.info('%r completed with status %d', command, return_code)
            except asyncio.CancelledError:
                log.info('Tearing down')
                proc.terminate()
                self.stats[command.id].return_code = await proc.wait()
                self.stats[command.id].status = JobStatus.INTERRUPTED
                break
            finally:
                try:
                    proc.kill()
                except OSError:
                    pass
                stdout.close()
                stderr.close()
        log.info("Worker terminated")

    async def serve_forever(self):
        log.info('Starting server')
        socket = self.zmq_ctx.socket(zmq.REP)
        log.debug('REP socket created')
        socket.bind(self.address)
        log.info('Socket bound to addr %s', self.address)
        while True:
            log.debug('Awaiting message')
            message = await socket.recv_json()
            if message['method'] == 'GET':
                response = self.do_GET(message)
            elif message['method'] == 'POST':
                response = self.do_POST(message)
            else:
                response = {
                    'ok': False,
                    'error': 'invalid-method'
                }
            socket.send_json(response)

    def do_GET(self, content):
        status = self.stats.get(content['id'])
        if status is None:
            return {
                'ok': True,
                'id': content['id'],
                'status': JobStatus.UNDEFINED,
                'returncode': None
            }
        else:
            return {
                'ok': True,
                'id': content['id'],
                'status': status.status,
                'returncode': status.return_code
            }

    def do_POST(self, content):
        log.debug("Processing POST")
        cmd = ShellCommandWrapper(
            cmd=content['cmd'],
            cwd=content['cwd'],
            env=content.get('env')
        )
        get_running_loop().call_soon(self.queue.put_nowait, cmd)
        self.stats[cmd.id] = ProcessStatus()
        log.info('Submitted %r', cmd)
        return {
            'ok': True,
            'id': cmd.id,
            'status': JobStatus.QUEUED,
            'returncode': None
        }

    def close(self):
        for worker in self.workers:
            worker.cancel()
        self.server.cancel()

    async def wait_closed(self):
        await asyncio.gather(
            self.server, *self.workers,
            return_exceptions=True
        )

    def run(self, loop=None):
        loop = loop or asyncio.get_event_loop()
        if self.workers:
            raise RuntimeError("Workers are already running")
        self.workers = [
            loop.create_task(self._worker(self.queue))
            for _ in range(self.num_workers)
        ]
        log.info('Workers created')
        if self.server is not None:
            raise RuntimeError("Server is already running.")
        self.server = loop.create_task(self.serve_forever())
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                self.close()
                loop.run_until_complete(self.wait_closed())
                loop.run_until_complete(loop.shutdown_asyncgens())
                self.workers.clear()
                self.server = None
            finally:
                loop.close()
