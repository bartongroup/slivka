import asyncio

import click

import slivka.conf.logging

from .client import LocalQueueClient, RequestError
from .core import ProcessStatus, LocalQueue


@click.command()
@click.option('--workers', '-w', type=click.INT, default=2)
@click.argument('address')
def main(address, workers):
    slivka.conf.logging.configure_logging()
    loop = asyncio.get_event_loop()
    local_queue = LocalQueue(
        address=address,
        protocol='ipc' if '/' in address else 'tcp',
        workers=workers
    )
    local_queue.run(loop)
