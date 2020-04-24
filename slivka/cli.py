import multiprocessing
import os
import signal
import sys
from contextlib import closing
from importlib import import_module
from logging.handlers import RotatingFileHandler

import click

from slivka.__about__ import __version__
from slivka.utils import nullcontext


@click.group()
@click.version_option(__version__)
def main():
    pass


@main.group('init')
@click.argument("path", type=click.Path(writable=True))
def init(path):
    """Initialize a new project in the directory specified."""
    path = os.path.abspath(os.path.join(os.curdir, path))
    if os.path.isdir(path):
        click.confirm(
            "Directory %s already exists. "
            "Do you want to overwrite its content?" % path,
            abort=True
        )
    init_project(path)


def init_project(base_dir):
    import shutil
    import stat
    import string
    from base64 import b64encode
    import pkg_resources

    # create directories
    for dn in ['bin', 'conf', 'scripts']:
        os.makedirs(os.path.join(base_dir, dn), exist_ok=True)

    # copy core files
    for fn in ['manage.py', 'services.yml', 'wsgi.py']:
        with open(os.path.join(base_dir, fn), 'wb') as dst:
            src = pkg_resources.resource_stream(
                'slivka.conf', 'project_template/' + fn
            )
            shutil.copyfileobj(src, dst)
    os.chmod(os.path.join(base_dir, 'manage.py'), stat.S_IRWXU)

    # create settings.yml
    tpl = pkg_resources.resource_string(
        'slivka.conf', 'project_template/settings.yml.tpl'
    )
    with open(os.path.join(base_dir, 'settings.yml'), 'w') as dst:
        dst.write(string.Template(tpl.decode()).substitute(
            base_dir=base_dir,
            secret_key=b64encode(os.urandom(24)).decode()
        ))

    # copy conf/*
    lstdir = pkg_resources.resource_listdir(
        'slivka.conf', 'project_template/conf'
    )
    for fn in lstdir:
        with open(os.path.join(base_dir, 'conf', fn), 'wb') as dst:
            src = pkg_resources.resource_stream(
                'slivka.conf', 'project_template/conf/' + fn
            )
            shutil.copyfileobj(src, dst)

    # copy scripts/*
    lstdir = pkg_resources.resource_listdir(
        'slivka.conf', 'project_template/scripts'
    )
    for fn in lstdir:
        with open(os.path.join(base_dir, 'scripts', fn), 'wb') as dst:
            src = pkg_resources.resource_stream(
                'slivka.conf', 'project_template/scripts/' + fn
            )
            shutil.copyfileobj(src, dst)
    os.chmod(os.path.join(base_dir, 'scripts', 'example.py'), stat.S_IRWXU)


@main.group('start')
@click.option('--home', '-h', type=click.Path())
def start(home):
    if home is not None:
        os.environ['SLIVKA_HOME'] = os.path.abspath(home)


@start.command('server')
@click.option('--type', '-t', 'server_type', default='devel',
              type=click.Choice(['gunicorn', 'uwsgi', 'devel']))
@click.option('--daemon/--no-daemon', '-d')
@click.option('--pid-file', '-p', default=None, type=click.Path(writable=True))
@click.option('--workers', '-w', default=None, type=click.INT)
@click.option('--http-socket', '-s')
def start_server(server_type, daemon, pid_file, workers, http_socket):
    import slivka
    if http_socket is None:
        http_socket = '{host}:{port}'.format(
            host=slivka.settings.server_host,
            port=slivka.settings.server_port
        )
    workers = workers or min(2 * multiprocessing.cpu_count() + 1, 12)
    if server_type == 'devel':
        if daemon:
            raise click.BadOptionUsage(
                'daemon', 'Cannot daemonize development server.')
        if pid_file:
            raise click.BadOptionUsage(
                'pid-file', 'Cannot use pid file with development server.')
        sys.path.append(slivka.settings.base_dir)
        import werkzeug
        host, port = http_socket.split(':')
        return werkzeug.run_simple(
            host, int(port), import_module('wsgi').application)
    if server_type == 'gunicorn':
        args = ['gunicorn',
                '--bind', http_socket,
                '--workers', str(workers),
                '--name', 'slivka-http',
                '--pythonpath', slivka.settings.base_dir]
        if daemon:
            args.append('--daemon')
        if pid_file:
            args.extend(['--pid', pid_file])
        args.append('wsgi:app')
    elif server_type == 'uwsgi':
        args = ['uwsgi',
                '--http-socket', http_socket,
                '--master',
                '--processes', str(workers),
                '--procname', 'slivka-http',
                '--module', 'wsgi',
                '--pythonpath', slivka.settings.base_dir]
        if daemon:
            args.append('--daemon')
        if pid_file:
            args.extend((['--pid', pid_file]))
    else:
        raise click.exceptions.BadParameter(
            'Invalid server type', param='server_type')
    os.execvp(args[0], args)


@start.command('scheduler')
@click.option('--daemon/--no-daemon', '-d')
@click.option('--pid-file', '-p', default=None, type=click.Path(writable=True))
def start_scheduler(daemon, pid_file):
    import slivka
    if daemon:
        slivka.utils.daemonize()
    pid_file_cm = (slivka.utils.PidFile(pid_file)
                  if pid_file else nullcontext())

    import slivka.conf.logging
    import slivka.scheduler
    from slivka.conf import settings

    sys.path.append(settings.base_dir)
    slivka.conf.logging.configure_logging()

    def terminate(_signum, _stack): scheduler.stop()
    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)

    handler = RotatingFileHandler(
        os.path.join(settings.logs_dir, 'slivka.log'),
        maxBytes=10 ** 8
    )
    listener = slivka.conf.logging.ZMQQueueListener(
        slivka.conf.logging.get_logging_sock(), (handler,)
    )
    with pid_file_cm, listener, closing(handler):
        scheduler = slivka.scheduler.Scheduler()
        for service in settings.services.values():
            scheduler.load_runners(service.name, service.command)
        scheduler.run_forever()


@start.command('local-queue')
@click.option('--address', '-a')
@click.option('--workers', '-w', default=2)
@click.option('--daemon/--no-daemon', '-d')
@click.option('--pid-file', '-p', default=None, type=click.Path(writable=True))
def start_local_queue(address, workers, daemon, pid_file):
    import slivka
    if daemon:
        slivka.utils.daemonize()
    pid_file_cm = (slivka.utils.PidFile(pid_file)
                   if pid_file else nullcontext())

    import asyncio
    import slivka.conf.logging
    from slivka.conf import settings
    from slivka.local_queue import LocalQueue
    slivka.conf.logging.configure_logging()
    os.environ.setdefault('SLIVKA_SECRET', settings.secret_key)

    loop = asyncio.get_event_loop()
    queue = LocalQueue(
        address=address or settings.slivka_queue_address,
        workers=workers
    )
    loop.add_signal_handler(signal.SIGTERM, queue.stop)
    loop.add_signal_handler(signal.SIGINT, queue.stop)
    with pid_file_cm, closing(queue):
        queue.run(loop)
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()


@start.command('shell',
               help='Set-up slivka and start interactive python console.')
def start_shell():
    import code
    code.interact()
