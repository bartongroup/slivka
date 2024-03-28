import logging
import logging.handlers
import unittest

import pytest
import slivka.conf.logging
import zmq
from hamcrest import assert_that, has_entries, has_properties
from slivka.conf.logging import ZMQQueueHandler, ZMQQueueListener


@pytest.fixture(scope="module")
def address():
    return "tcp://localhost:13231"


@pytest.fixture()
def logger():
    return logging.Logger("test.logging", level=logging.DEBUG)


@pytest.fixture()
def pull_socket(address):
    ctx = zmq.Context.instance()
    socket: zmq.Socket = ctx.socket(zmq.PULL)
    socket.bind(address)
    yield socket
    socket.close(0)


@pytest.fixture()
def mock_handler():
    handler = logging.Handler()
    with unittest.mock.patch.object(handler, "emit"):
        yield handler


def test_handler_record_sent(address, logger, pull_socket):
    handler = ZMQQueueHandler(address)
    logger.addHandler(handler)
    logger.error("Error message")
    data = pull_socket.recv_json()
    # noinspection PyTypeChecker
    assert_that(
        data,
        has_entries(
            name="test.logging",
            msg="Error message",
            levelname="ERROR",
            levelno=logging.ERROR,
        ),
    )


def test_listener_record_received(logger, address, mock_handler):
    logger.addHandler(ZMQQueueHandler(address))
    listener = ZMQQueueListener(address, handlers=(mock_handler,))
    logger.info("info message")
    record = listener.dequeue(True)
    assert_that(
        record,
        has_properties(
            "name", "test.logging",
            "msg", "info message",
            "levelname", "INFO",
            "levelno", logging.INFO,
            "exc_info", None,
            "exc_text", None,
        ),
    )


def test_configure_logging(minimal_project, mock_handler):
    slivka.conf.logging.configure_logging()
    addr = slivka.conf.logging.get_logging_sock()
    listener = ZMQQueueListener(addr, handlers=(mock_handler,))
    logger = logging.getLogger("slivka")
    logger.info("info message")
    record = listener.dequeue(True)
    assert record.name == "slivka"
