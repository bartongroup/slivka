"""Entry points for command line interface.

This module provides a collection of functions which are called directly from
the command line interface. Each function corresponds to the command with the
same name as the function, which is passed as a first parameter to the script
call. Additionally, some of the functions process additional arguments
usually specified just after the command name.
"""
import os
import shutil
import stat
from base64 import b64encode
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

    This function initializes a new project in the current working directory
    and populates it with necessary directory tree and configuration files.
    Project name should be specified as a command argument and corresponds to
    the name of the new project folder.
    Using ``"."`` (dot) as a folder name will set up the project in the current
    directory.

    All templates are fetched form ``slivka/data/template`` populated
    with data specific to the project and copied to the project directory.

    Calling this function is a default behaviour when the slivka module is
    executed.

    :param name: name of the project folder
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
def start_workers():
    """Start task queue workers."""
    os.environ.setdefault('SLIVKA_SECRET', slivka.settings.SECRET_KEY)
    os.execlp('python', 'python', '-m', 'slivka.local_queue',
              slivka.settings.SLIVKA_QUEUE_ADDR)


@click.command('scheduler')
def start_scheduler():
    """Start job scheduler."""
    from slivka.scheduler import Scheduler
    slivka.conf.logging.configure_logging()
    handler = RotatingFileHandler(
        os.path.join(slivka.settings.BASE_DIR, 'logs', 'slivka.log'),
        maxBytes=100e6
    )
    listener = slivka.conf.logging.ZMQQueueListener(
        'ipc:///tmp/slivka.logging.sock', (handler,)
    )
    with listener:
        scheduler = Scheduler()
        for service, conf in slivka.settings.service_configurations.items():
            scheduler.load_service(service, conf.command_def)
        scheduler.run_forever()


@click.command('server')
@click.option('--server-type', '-t', default='devel',
              type=click.Choice(['gunicorn', 'devel']))
def start_server(server_type):
    """Start HTTP server."""
    host = slivka.settings.SERVER_HOST
    port = int(slivka.settings.SERVER_PORT)
    if server_type == 'devel':
        from slivka.server.serverapp import app
        app.run(host=host, port=port, debug=True)
    elif server_type == 'gunicorn':
        os.chdir(slivka.settings.BASE_DIR)
        os.execlp('gunicorn', 'gunicorn',
                  '--bind=%s:%d' % (host, port),
                  '--workers=4',
                  '--name=slivka-http',
                  'wsgi:app')


@click.command()
def shell():
    """Start an interactive shell."""
    import code
    code.interact()


@click.command('check')
def check():
    try:
        slivka.settings.BASE_DIR
    except Exception:
        raise
    else:
        click.echo("OK")


manager.add_command(start_workers)
manager.add_command(start_scheduler)
manager.add_command(start_server)
manager.add_command(shell)
manager.add_command(check)
