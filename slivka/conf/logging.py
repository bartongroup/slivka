import atexit
import logging.config
import logging.handlers
import os
import tempfile

import zmq

import slivka

_context = zmq.Context()
atexit.register(_context.destroy, 0)


class ZMQQueueHandler(logging.handlers.QueueHandler):
    def __init__(self, address, ctx: zmq.Context = None):
        ctx = ctx or _context
        socket = ctx.socket(zmq.PUSH)
        socket.connect(address)
        super().__init__(socket)

    def enqueue(self, record):
        self.queue.send_json(record.__dict__)

    def close(self):
        super().close()
        self.queue.close()


class ZMQQueueListener(logging.handlers.QueueListener):
    def __init__(self, address, handlers=(), ctx: zmq.Context = None):
        self._address = address
        self._ctx = ctx or _context
        socket = self._ctx.socket(zmq.PULL)
        socket.bind(address)
        super().__init__(socket, *handlers, respect_handler_level=False)

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def dequeue(self, block):
        msg = self.queue.recv_json()
        if msg == self._sentinel:
            return msg
        else:
            return logging.makeLogRecord(msg)

    def enqueue_sentinel(self):
        socket = self._ctx.socket(zmq.PUSH)
        socket.connect(self._address)
        socket.send_json(self._sentinel)

    def stop(self):
        super().stop()
        self.queue.close(0)
        if self._address.startswith('ipc://'):
            os.unlink(self._address[6:])


def get_logging_sock():
    from hashlib import md5
    from base64 import b64encode
    home = slivka.conf.settings.directory.home
    suffix = b64encode(md5(home.encode()).digest()[:6], b'-_').decode()
    tmp = tempfile.gettempdir()
    path = 'ipc://%s/slivka-logging-%s.sock' % (tmp, suffix)
    return path


def configure_logging(level=logging.DEBUG):
    if isinstance(level, str):
        level = logging.getLevelName(level)

    zmq_handler = ZMQQueueHandler(get_logging_sock())
    zmq_handler.setLevel(level)
    full_formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    zmq_handler.setFormatter(full_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    minimal_formatter = logging.Formatter(fmt="%(levelname)-8s %(message)s")
    console_handler.setFormatter(minimal_formatter)

    logger = logging.getLogger("slivka")
    logger.propagate = False
    logger.setLevel(level)
    logger.addHandler(zmq_handler)
    logger.addHandler(console_handler)
