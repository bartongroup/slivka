"""Entry points for command line interface.

This module provides a collection of functions which are called directly from
the command line interface. Each function corresponds to the command with the
same name as the function, which is passed as a first parameter to the script
call. Additionally, some of the functions process additional arguments
usually specified just after the command name.
"""
import atexit
import multiprocessing
import os
import shutil
import signal
import stat
from base64 import b64encode
from importlib import import_module
from logging.handlers import RotatingFileHandler
from string import Template

import click
import pkg_resources

import slivka
import slivka.conf.logging
import slivka.utils


@click.command()
@click.argument("name")
def setup(name):
    """Setup a new project in the current working directory.

    This function initializes a new project in the specified directory
    and project and example files in it.
    Using ``"."`` (dot) as a folder name will set up the project in the current
    directory.
    """
    project_dir = os.path.abspath(os.path.join(os.getcwd(), name))
    if os.path.isdir(project_dir):
        click.confirm(
            "Directory already exist. Do you want to set the project here?",
            abort=True
        )
    init_project(project_dir)


def init_project(base_dir):
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
        dst.write(Template(tpl.decode()).substitute(
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


@click.group()
def manager():
    os.environ['SLIVKA_HOME'] = slivka.settings.BASE_DIR


@click.command('local-queue')
@click.option('--address', '-a')
@click.option('--workers', '-w', default=2)
@click.option('--daemon/--no-daemon', '-d')
@click.option('--pid-file', '-p', default=None, type=click.Path(writable=True))
def start_workers(address, workers, daemon, pid_file):
    """Start task queue workers."""
    if daemon:
        slivka.utils.daemonize()
    import asyncio
    import contextlib
    from slivka.local_queue import LocalQueue
    slivka.conf.logging.configure_logging()
    os.environ.setdefault('SLIVKA_SECRET', slivka.settings.SECRET_KEY)

    loop = asyncio.get_event_loop()
    queue = LocalQueue(
        address=address or slivka.settings.SLIVKA_QUEUE_ADDR,
        workers=workers
    )

    if pid_file:
        with open(pid_file, 'w') as f:
            f.write("%d\n" % os.getpid())
        atexit.register(os.remove, pid_file)

    def terminate(signum): queue.stop()
    loop.add_signal_handler(signal.SIGTERM, terminate, signal.SIGTERM)
    loop.add_signal_handler(signal.SIGINT, terminate, signal.SIGINT)

    with contextlib.closing(queue):
        queue.run(loop)
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()


@click.command('scheduler')
@click.option('--daemon/--no-daemon', '-d')
@click.option('--pid-file', '-p', default=None, type=click.Path(writable=True))
def start_scheduler(daemon, pid_file):
    """Start job scheduler."""
    if daemon:
        slivka.utils.daemonize()
    from slivka.scheduler import Scheduler
    slivka.conf.logging.configure_logging()
    handler = RotatingFileHandler(
        os.path.join(slivka.settings.BASE_DIR, 'logs', 'slivka.log'),
        maxBytes=100e6
    )
    atexit.register(handler.close)
    listener = slivka.conf.logging.ZMQQueueListener(
        'ipc:///tmp/slivka.logging.sock', (handler,)
    )

    if pid_file:
        with open(pid_file, 'w') as f:
            f.write("%d\n" % os.getpid())
        atexit.register(os.remove, pid_file)

    def terminate(signum, stack_frame): scheduler.stop()
    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)

    with listener:
        scheduler = Scheduler()
        for service, conf in slivka.settings.service_configurations.items():
            scheduler.load_service(service, conf.command_def)
        scheduler.run_forever()


@click.command('server')
@click.option('--type', '-t', 'server_type', default='devel',
              type=click.Choice(['gunicorn', 'uwsgi', 'devel']))
@click.option('--daemon/--no-daemon', '-d')
@click.option('--pid-file', '-p', default=None, type=click.Path(writable=True))
@click.option('--workers', '-w', default=None, type=click.INT)
def start_server(server_type, daemon, pid_file, workers):
    """Start HTTP server."""
    host = slivka.settings.SERVER_HOST
    port = int(slivka.settings.SERVER_PORT)
    workers = workers or min(2 * multiprocessing.cpu_count() + 1, 12)
    os.chdir(slivka.settings.BASE_DIR)
    if server_type == 'devel':
        if daemon:
            raise click.BadOptionUsage('daemon', "Cannot daemonize development server.")
        if pid_file:
            raise click.BadOptionUsage('pid-file', 'Cannot use pid file with development server type.')
        from werkzeug.serving import run_simple
        run_simple(host, port, import_module('wsgi').application)
    elif server_type == 'gunicorn':
        args = ['gunicorn',
                '--bind=%s:%d' % (host, port),
                '--workers=%d' % workers,
                '--name=slivka-http']
        if daemon:
            args.append('--daemon')
        if pid_file:
            args.extend(['--pid', pid_file])
        args.append('wsgi:app')
        os.execvp(args[0], args)
    elif server_type == 'uwsgi':
        args = ['uwsgi',
                '--http-socket', '%s:%d' % (host, port),
                '--wsgi-file', 'wsgi.py',
                '--master',
                '--processes', str(workers),
                '--procname', 'slivka-http']
        if daemon:
            args.append('--daemonize')
        if pid_file:
            args.extend(['--pidfile', pid_file])
        os.execvp(args[0], args)


@click.command()
def shell():
    """Start an interactive shell."""
    import code
    code.interact()


@click.command('test-services')
@click.option('--keep-work-dirs', is_flag=1)
def check_runners(keep_work_dirs):
    """Perform a check of all configured runners."""
    import slivka.scheduler.system_check
    directory = os.path.join(slivka.settings.BASE_DIR, 'tests')
    exit(slivka.scheduler.system_check.test_all(directory, not keep_work_dirs))


manager.add_command(start_workers)
manager.add_command(start_scheduler)
manager.add_command(start_server)
manager.add_command(shell)
manager.add_command(check_runners)
