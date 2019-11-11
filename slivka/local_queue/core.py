import asyncio
from typing import Dict

import itertools
import logging
import os
import time

import zmq
import zmq.asyncio as aiozmq

from slivka import JobStatus


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
        return "Command(id=%s, cmd=%s, cwd=%s)" % (self.id, self.cmd, self.cwd)


class ProcessStatus:
    def __init__(self):
        self.status = JobStatus.QUEUED
        self.return_code = None


class LocalQueue:
    zmq_ctx = aiozmq.Context()

    def __init__(self, address, protocol='tcp', workers=1, secret=None):
        self.logger = logging.getLogger(__name__)
        self.address = protocol + '://' + address
        self.num_workers = workers
        self.secret = secret
        if not secret:
            self.logger.warning('No secret used.')
        self.server = None
        self.queue = asyncio.Queue()
        self.workers = []
        self.stats = {}  # type: Dict[int, ProcessStatus]

    async def _worker(self, queue):
        self.logger.info("worker spawned")
        while True:
            self.logger.debug('waiting for the command')
            command = await queue.get()  # type: ShellCommandWrapper
            self.logger.info('executing %r', command)
            try:
                stdout = open(os.path.join(command.cwd, 'stdout'), 'wb')
                stderr = open(os.path.join(command.cwd, 'stderr'), 'wb')
                proc = await asyncio.create_subprocess_shell(
                    command.cmd,
                    stdout=stdout,
                    stderr=stderr,
                    cwd=command.cwd,
                    env=command.env
                )
            except OSError:
                self.logger.exception(
                    "System error occurred when starting the job %r", command)
                self.stats[command.id].status = JobStatus.ERROR
                continue
            else:
                self.stats[command.id].status = JobStatus.RUNNING
            try:
                return_code = await proc.wait()
                self.stats[command.id].return_code = return_code
                self.stats[command.id].status = (
                    JobStatus.COMPLETED if return_code == 0 else
                    JobStatus.FAILED if return_code > 0 else
                    JobStatus.INTERRUPTED
                )
                self.logger.info('%r completed with status %d', command, return_code)
            except asyncio.CancelledError:
                self.logger.info('terminating a running process')
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

    async def serve_forever(self):
        self.logger.info('starting server')
        socket = self.zmq_ctx.socket(zmq.REP)
        socket.bind(self.address)
        self.logger.info('REP socket bound to %s', self.address)
        while True:
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
        return {
            'ok': True,
            'id': content['id'],
            'status': status.status if status is not None else JobStatus.UNKNOWN,
            'returncode': status.return_code if status is not None else None
        }

    def do_POST(self, content):
        cmd = ShellCommandWrapper(
            cmd=content['cmd'],
            cwd=content['cwd'],
            env=content.get('env')
        )
        get_running_loop().call_soon(self.queue.put_nowait, cmd)
        self.stats[cmd.id] = ProcessStatus()
        self.logger.info('queued %r for execution', cmd)
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
        if self.server is not None:
            raise RuntimeError("Server is already running.")
        self.server = loop.create_task(self.serve_forever())
        try:
            loop.run_until_complete(asyncio.gather(*self.workers, self.server))
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
