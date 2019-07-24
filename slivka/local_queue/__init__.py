import asyncio
import logging
import os

import click

from .client import LocalQueueClient, RequestError
from .core import Status, ProcessStatus, LocalQueue


@click.command()
@click.option('--port', '-p', type=click.IntRange(1024, 49151), metavar="PORT")
@click.option('--socket', '-s', type=click.Path())
@click.option('--workers', '-w', type=click.INT, default=2)
@click.option('--log-level', default='INFO')
def main(port, socket, workers, log_level):
    logging.basicConfig(level=log_level)
    logging.getLogger('slivka-queue').setLevel(log_level)
    loop = asyncio.get_event_loop()
    local_queue = LocalQueue(
        socket or ('localhost', port),
        workers=workers,
        secret=os.getenvb(b'SLIVKA_SECRET')
    )
    local_queue.run(loop)
