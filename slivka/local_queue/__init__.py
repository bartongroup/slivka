import asyncio
import logging

import click

from .client import LocalQueueClient, RequestError
from .core import Status, ProcessStatus, LocalQueue


@click.command()
@click.option('--address', '-b')
@click.option('--workers', '-w', type=click.INT, default=2)
@click.option('--log-level', default='INFO')
def main(address, workers, log_level):
    logging.basicConfig(level=log_level)
    logging.getLogger('slivka-queue').setLevel(log_level)
    loop = asyncio.get_event_loop()
    local_queue = LocalQueue(
        address=address,
        protocol='ipc' if '/' in address else 'tcp',
        workers=workers
    )
    local_queue.run(loop)
