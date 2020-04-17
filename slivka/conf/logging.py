import atexit
import logging.config
import logging.handlers
import os

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

    def emit(self, record):
        message = self.format(record)
        msg = record.__dict__.copy()
        msg.update(
            message=message,
            msg=message,
            args=None,
            exc_info=None,
            exc_text=None
        )
        self.queue.send_json(msg)


class ZMQQueueListener(logging.handlers.QueueListener):
    def __init__(self, address, handlers=(), ctx: zmq.Context = None):
        self._address = address
        ctx = ctx or _context
        self._ctx = ctx
        socket = ctx.socket(zmq.PULL)
        socket.bind(address)
        super().__init__(socket, *handlers, respect_handler_level=False)
        self.handlers = list(self.handlers)

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        self.cleanup()

    def add_handler(self, handler):
        self.handlers.append(handler)

    def remove_handler(self, handler):
        self.handlers.remove(handler)

    def dequeue(self, block):
        msg = self.queue.recv_json()
        if msg == self._sentinel:
            self.queue.close(0)
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

    def cleanup(self):
        if self._address.startswith('ipc://'):
            os.unlink(self._address[6:])


def get_logging_sock():
    from hashlib import md5
    from base64 import b64encode
    home = slivka.settings.base_dir
    suffix = b64encode(md5(home.encode()).digest()[:6], b'-_').decode()
    tmp = os.environ.get('TEMP') or os.environ.get('TMP') or '/tmp'
    path = 'ipc://%s/slivka-logging_%s.sock' % (tmp, suffix)
    return path


def _get_default_logging_config():
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'full': {
                'format': "%(asctime)s %(levelname)-10s %(name)s %(message)s",
                'datefmt': "%d/%m/%y %H:%M:%S"
            },
            'minimal': {
                'format': '%(levelname)s %(message)s'
            }
        },
        'handlers': {
            'slivka.logging_queue': {
                'class': 'slivka.conf.logging.ZMQQueueHandler',
                'formatter': 'full',
                'level': 'DEBUG',
                'address': get_logging_sock()
            },
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'minimal',
                'level': 'DEBUG'
            }
        },
        'loggers': {
            'slivka': {
                'level': 'DEBUG',
                'propagate': False,
                'handlers': ['slivka.logging_queue', 'console']
            }
        }
    }


def configure_logging(config=None):
    config = config or _get_default_logging_config()
    logging.config.dictConfig(config)
