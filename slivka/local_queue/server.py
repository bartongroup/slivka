import asyncio
import itertools
import logging
import os
import re
import time
import urllib.parse
from functools import partial
from typing import Dict

import attr
import zmq
import zmq.asyncio as aiozmq

from slivka import JobStatus
from slivka.utils import LimitedSizeDict

try:
    get_running_loop = asyncio.get_running_loop
except AttributeError:
    get_running_loop = asyncio.get_event_loop


_id_counter = itertools.count(0)


def _job_id_factory():
    return int(time.time()) << 32 | (next(_id_counter) & 0xffffffff)


def _job_env_converter(env):
    env.setdefault("PATH", os.getenv("PATH"))
    return env


@attr.s(slots=True)
class Job:
    id = attr.ib(factory=_job_id_factory, init=False)
    cmd = attr.ib(type=str)
    cwd = attr.ib(type=str)
    env = attr.ib(default={}, type=dict, converter=_job_env_converter, repr=False)
    state = attr.ib(default=JobStatus.QUEUED)
    return_code = attr.ib(default=255, type=int, init=False)
    worker = attr.ib(default=None, type=asyncio.Task, init=False, repr=False)


_null_job = Job('', '', state=JobStatus.UNKNOWN)


class LocalQueue:
    zmq_ctx = aiozmq.Context()

    def __init__(self, address, workers=1, secret=None):
        self.logger = logging.getLogger(__name__)
        if not re.match(r'(\w*:)?//', address):
            # if only host given, assume tcp://
            address = "tcp://" + address
        elif address.startswith('unix://'):
            address = str.replace(address, 'unix', 'ipc', 1)
        self.address = urllib.parse.urlsplit(address, scheme="tcp").geturl()
        self.num_workers = workers
        self.secret = secret
        if not secret:
            self.logger.warning('No secret used.')
        self.queue = asyncio.Queue()
        self.workers = set()
        self.jobs = LimitedSizeDict(1000000)  # type: Dict[int, Job]
        self._main_coro = None

    async def _worker(self, job):
        self.logger.info('executing %r', job)
        job.state = JobStatus.RUNNING
        try:
            stdout = open(os.path.join(job.cwd, 'stdout'), 'wb')
            stderr = open(os.path.join(job.cwd, 'stderr'), 'wb')
            proc = await asyncio.create_subprocess_shell(
                job.cmd,
                stdout=stdout,
                stderr=stderr,
                cwd=job.cwd,
                env=job.env
            )
        except OSError:
            self.logger.exception(
                "System error occurred when starting the job %r", job)
            job.state = JobStatus.ERROR
            raise
        except asyncio.CancelledError:
            job.state = JobStatus.INTERRUPTED
            return
        try:
            return_code = await proc.wait()
            job.return_code = return_code
            job.state = (
                JobStatus.COMPLETED if return_code == 0 else
                JobStatus.ERROR if return_code == 127 else
                JobStatus.FAILED if return_code > 0 else
                JobStatus.INTERRUPTED
            )
            self.logger.info('%r completed with status %d', job, return_code)
        except asyncio.CancelledError:
            self.logger.info('terminating a running process')
            proc.terminate()
            job.return_code = await proc.wait()
            job.state = JobStatus.INTERRUPTED
        finally:
            try:
                proc.kill()
            except OSError:
                pass
            stdout.close()
            stderr.close()

    async def _consumer(self, loop):
        lock = asyncio.BoundedSemaphore(self.num_workers)

        def worker_cleanup(job: Job, fut: asyncio.Future):
            lock.release()
            job.worker = None
            self.workers.remove(fut)
            if fut.exception() is not None:
                self.logger.error(
                    "An exception occurred when running a job %r",
                    fut.exception()
                )

        while True:
            await lock.acquire()
            job = await self.queue.get()
            if job.state != JobStatus.QUEUED:
                lock.release()
                continue
            assert job.id in self.jobs
            worker = loop.create_task(self._worker(job))  # type: asyncio.Task
            self.workers.add(worker)
            job.worker = worker
            worker.add_done_callback(partial(worker_cleanup, job))

    async def serve_forever(self):
        self.logger.info('starting server')
        socket = self.zmq_ctx.socket(zmq.REP)
        socket.bind(self.address)
        self.logger.info('REP socket bound to %s', self.address)
        while True:
            message = await socket.recv_json()
            try:
                if message['method'] == 'GET':
                    response = self.do_GET(message)
                elif message['method'] == 'POST':
                    response = self.do_POST(message)
                elif message['method'] == 'CANCEL':
                    response = self.do_CANCEL(message)
                elif message['method'] == 'DELETE':
                    response = self.do_DELETE(message)
                else:
                    response = {
                        'ok': False,
                        'error': 'invalid-method'
                    }
            except Exception:
                self.logger.exception("Error during message processing")
                response = {
                    'ok': False,
                    'error': 'invalid-message'
                }
            socket.send_json(response)

    def do_GET(self, msg):
        job = self.jobs.get(msg['id'], _null_job)
        return {
            'ok': True,
            'id': job.id,
            'state': job.state,
            'returncode': job.return_code
        }

    def do_POST(self, msg):
        job = Job(
            cmd=msg['cmd'],
            cwd=msg['cwd'],
            env=msg.get('env', {})
        )
        self.jobs[job.id] = job
        get_running_loop().call_soon(self.queue.put_nowait, job)
        self.logger.info('queued %r for execution', job)
        return {
            'ok': True,
            'id': job.id,
            'state': job.state,
            'returncode': None
        }

    def do_CANCEL(self, msg):
        job = self.jobs.get(msg['id'], _null_job)
        if job.state == JobStatus.QUEUED:
            job.state = JobStatus.INTERRUPTED
        if job.worker is not None:
            job.worker.cancel()
        return {
            'ok': True
        }

    def do_DELETE(self, msg):
        try:
            job = self.jobs[msg['id']]
            job.state = JobStatus.DELETED
            del self.jobs[job.id]
        except KeyError:
            pass
        return {
            'ok': True
        }

    def stop(self):
        self.logger.info("Stopping.")
        for worker in self.workers:
            worker.cancel()
        self._main_coro.cancel()

    def close(self, loop=None):
        self.logger.info("Closing.")
        loop = loop or asyncio.get_event_loop()
        loop.run_until_complete(self.wait_closed())
        self.workers.clear()
        self._main_coro = None
        self.logger.info('Closed.')

    async def wait_closed(self):
        await asyncio.gather(
            self._main_coro, *self.workers,
            return_exceptions=True
        )

    def run(self, loop=None):
        if self._main_coro is not None:
            raise RuntimeError("Scheduler is already running.")
        loop = loop or asyncio.get_event_loop()
        server = loop.create_task(self.serve_forever())
        consumer = loop.create_task(self._consumer(loop))
        self._main_coro = asyncio.gather(server, consumer)
        try:
            loop.run_until_complete(self._main_coro)
        except KeyboardInterrupt:
            self.stop()
        except asyncio.CancelledError:
            pass
        self.logger.info('Stopped.')
