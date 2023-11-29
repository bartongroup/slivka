import datetime
import multiprocessing
import os
import signal
import sys
from contextlib import closing
from importlib import import_module
from logging.handlers import RotatingFileHandler

import click
from daemon import DaemonContext
from daemon.pidfile import TimeoutPIDLockFile

from slivka.__about__ import __version__
from slivka.compat.contextlib import nullcontext
from slivka.utils.daemon import DummyDaemonContext


@click.group()
@click.version_option(__version__)
def main():
    pass


@main.command('init')
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
    from slivka.compat import resources

    def copy_project_file(src, dst=None):
        if dst is None: dst = src
        dst = os.path.join(base_dir, dst)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f:
            stream = resources.open_binary(
                'slivka', 'project_template/' + src
            )
            shutil.copyfileobj(stream, f)

    click.echo("Creating project directory.")
    click.echo("Copying files.")
    copy_project_file("manage.py")
    os.chmod(os.path.join(base_dir, "manage.py"), stat.S_IRWXU)
    copy_project_file("settings.yaml", "config.yaml")
    copy_project_file("wsgi.py")
    copy_project_file("services/example.service.yaml")
    copy_project_file("scripts/selectors.py")
    copy_project_file("scripts/example.py")
    os.chmod(os.path.join(base_dir, 'scripts', 'example.py'), stat.S_IRWXU)
    copy_project_file("static/openapi.yaml")
    copy_project_file("static/redoc-index.html")
    click.echo("Done.")


@main.group('start')
@click.option('--home', '-h', type=click.Path())
def start(home):
    if home is None:
        home = os.getenv('SLIVKA_HOME', os.getcwd())
    os.environ['SLIVKA_HOME'] = os.path.abspath(home)


@start.command('server')
@click.option('--type', '-t', 'server_type', default='devel',
              type=click.Choice(['gunicorn', 'uwsgi', 'devel']))
@click.option('--daemon/--no-daemon', '-d')
@click.option('--pid-file', '-p', default=None,
              type=click.Path(writable=True, resolve_path=True))
@click.option('--workers', '-w', default=None, type=click.INT)
@click.option('--http-socket', '-s')
def start_server(server_type, daemon, pid_file, workers, http_socket):
    from slivka.conf import settings
    os.environ.setdefault('SLIVKA_HOME', settings.directory.home)

    if http_socket is None:
        http_socket = settings.server.host
    workers = workers or min(2 * multiprocessing.cpu_count() + 1, 12)
    if server_type == 'devel':
        if daemon:
            raise click.BadOptionUsage(
                'daemon', 'Cannot daemonize development server.')
        if pid_file:
            raise click.BadOptionUsage(
                'pid-file', 'Cannot use pid file with development server.')
        sys.path.append(settings.directory.home)
        os.environ.setdefault('FLASK_DEBUG', "1")
        import werkzeug
        host, port = http_socket.split(':')
        return werkzeug.run_simple(host, int(port), import_module('wsgi').app)
    if server_type == 'gunicorn':
        args = ['gunicorn',
                '--bind', http_socket,
                '--workers', str(workers),
                '--name', 'slivka-http',
                '--pythonpath', settings.directory.home]
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
                '--pythonpath', settings.directory.home]
        if daemon:
            args.append('--daemon')
        if pid_file:
            args.extend(['--pid', pid_file])
    else:
        raise click.BadParameter('Invalid server type', param='server_type')
    os.execvp(args[0], args)


@start.command('scheduler')
@click.option('--daemon/--no-daemon', '-d')
@click.option('--pid-file', '-p', default=None,
              type=click.Path(writable=True, resolve_path=True))
def start_scheduler(daemon, pid_file):
    from slivka.conf import settings
    os.environ.setdefault('SLIVKA_HOME', settings.directory.home)
    sys.path.append(settings.directory.home)
    import slivka.conf.logging
    import slivka.scheduler
    from slivka.scheduler.factory import runners_from_config
    from slivka.scheduler.service_monitor import ServiceTest, ServiceTestExecutorThread
    from slivka.db.repositories import ServiceStatusMongoDBRepository

    def terminate_handler(_signum, _stack): scheduler.stop()
    signals = {
        signal.SIGINT: terminate_handler,
        signal.SIGTERM: terminate_handler,
    }
    pidfile_ctx = TimeoutPIDLockFile(pid_file) if pid_file else nullcontext()
    daemon_args = dict(
        pidfile=pidfile_ctx,
        signal_map=signals,
        stdout=None,
        stderr=None,
    )
    daemon_ctx = (DaemonContext(**daemon_args) if daemon
                  else DummyDaemonContext(**daemon_args))
    with daemon_ctx:
        slivka.conf.logging.configure_logging()
        handler = RotatingFileHandler(
            os.path.join(settings.directory.logs, 'slivka.log'),
            maxBytes=10 ** 8
        )
        listener = slivka.conf.logging.ZMQQueueListener(
            slivka.conf.logging.get_logging_sock(), (handler,)
        )
        with listener, closing(handler):
            scheduler = slivka.scheduler.Scheduler(settings.directory.jobs)
            service_monitor = ServiceTestExecutorThread(
                ServiceStatusMongoDBRepository(),
                interval=datetime.timedelta(hours=1),
            )
            for service_config in settings.services:
                selector, runners = runners_from_config(service_config)
                scheduler.add_selector(service_config.id, selector)
                for runner in runners:
                    scheduler.add_runner(runner)
                service_monitor.extend_tests(
                    ServiceTest(
                        runner=runner,
                        test_parameters=test_conf.parameters,
                        timeout=test_conf.timeout or 900
                    )
                    for runner in runners
                    for test_conf in service_config.tests
                    if runner.name in test_conf.applicable_runners
                )
            service_monitor.start()
            scheduler.run_forever()
            service_monitor.shutdown()


@start.command('local-queue')
@click.option('--address', '-a')
@click.option('--workers', '-w', default=2)
@click.option('--daemon/--no-daemon', '-d')
@click.option('--pid-file', '-p', default=None,
              type=click.Path(writable=True, resolve_path=True))
def start_local_queue(address, workers, daemon, pid_file):
    from slivka.conf import settings
    os.environ.setdefault('SLIVKA_HOME', settings.directory.home)
    sys.path.append(settings.directory.home)
    import asyncio
    import slivka.conf.logging
    from slivka.local_queue import LocalQueue

    pidfile_ctx = TimeoutPIDLockFile(pid_file) if pid_file else nullcontext()
    daemon_args = dict(
        pidfile=pidfile_ctx,
        stdout=None,
        stderr=None,
    )
    daemon_ctx = (DaemonContext(**daemon_args) if daemon
                  else DummyDaemonContext(**daemon_args))

    with daemon_ctx:
        slivka.conf.logging.configure_logging()
        loop = asyncio.get_event_loop()
        queue = LocalQueue(
            address=address or settings.local_queue.host, workers=workers
        )
        loop.add_signal_handler(signal.SIGTERM, queue.stop)
        loop.add_signal_handler(signal.SIGINT, queue.stop)
        with closing(queue):
            queue.run(loop)
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


@start.command('shell',
               help='Set-up slivka and start interactive python console.')
def start_shell():
    import code
    from slivka.conf import settings
    os.environ.setdefault('SLIVKA_HOME', settings.directory.home)
    sys.path.append(settings.directory.home)
    code.interact()
