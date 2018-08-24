"""Entry points for command line interface.

This module provides a collection of functions which are called directly from
the command line interface. Each function corresponds to the command with the
same name as the function, which is passed as a first parameter to the script
call. Additionally, some of the functions process additional arguments
usually specified just after the command name.
"""

import os
import stat
from base64 import b64encode

import click
import jinja2
import pkg_resources

import slivka
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
    ProjectBuilder(project_dir).build()


class ProjectBuilder:
    def __init__(self, project_dir):
        self._dir = project_dir

    def build(self):
        os.makedirs(self._dir, exist_ok=True)
        os.makedirs(os.path.join(self._dir, 'binaries'), exist_ok=True)
        os.makedirs(os.path.join(self._dir, 'configurations'), exist_ok=True)
        os.makedirs(os.path.join(self._dir, 'scripts'), exist_ok=True)
        self._make_manage()
        self._make_wsgi()
        self._make_settings()
        script_path = self._make_script()
        form_path = self._make_form()
        command_config_path = self._make_command_configuration(script_path)
        self._make_limits()
        self._make_services_ini(form_path, command_config_path)

    def _make_manage(self):
        path = os.path.join(self._dir, 'manage.py')
        with open(path, 'wb') as f:
            f.write(pkg_resources.resource_string(
                'slivka', 'data/template/manage.py'
            ))
        os.chmod(path, stat.S_IRWXU)

    def _make_wsgi(self):
        path = os.path.join(self._dir, 'wsgi.py')
        with open(path, 'wb') as f:
            f.write(pkg_resources.resource_string(
                'slivka', 'data/template/wsgi.py'
            ))

    def _make_settings(self):
        path = os.path.join(self._dir, 'settings.yml')
        template = jinja2.Template(
            pkg_resources.resource_string(
                'slivka', 'data/template/settings.yml.jinja2'
            ).decode()
        )
        stream = template.stream(
            base_dir=self._dir,
            secret_key=b64encode(os.urandom(32)).decode('utf-8')
        )
        with open(path, 'w') as f:
            stream.dump(f)

    def _make_script(self):
        path = os.path.join(self._dir, 'binaries', 'pydummy.py')
        with open(path, 'wb') as f:
            f.write(pkg_resources.resource_string(
                'slivka', 'data/template/binaries/pydummy.py'
            ))
        os.chmod(path, stat.S_IRWXU)
        return path

    def _make_form(self):
        path = os.path.join(self._dir, 'configurations', 'pydummyForm.yml')
        with open(path, 'wb') as f:
            f.write(pkg_resources.resource_string(
                'slivka', 'data/template/configurations/pydummyForm.yml'
            ))
        return path

    def _make_command_configuration(self, script_path):
        path = os.path.join(self._dir, 'configurations', 'pydummyCommand.yml')
        template = jinja2.Template(
            pkg_resources.resource_string(
                'slivka', 'data/template/configurations/pydummyCommand.yml'
            ).decode()
        )
        stream = template.stream(script=script_path)
        with open(path, 'w') as f:
            stream.dump(f)
        return path

    def _make_limits(self):
        path = os.path.join(self._dir, 'scripts', 'limits.py')
        with open(path, 'wb') as f:
            f.write(pkg_resources.resource_string(
                'slivka', 'data/template/scripts/limits.py'
            ))
        open(os.path.join(os.path.dirname(path), '__init__.py'), 'w').close()
        return path

    def _make_services_ini(self, form_path, command_config_path):
        path = os.path.join(self._dir, 'configurations', 'services.ini')
        template = jinja2.Template(
            pkg_resources.resource_string(
                'slivka', 'data/template/configurations/services.ini.jinja2'
            ).decode()
        )
        stream = template.stream(form_path=form_path,
                                 config_path=command_config_path)
        with open(path, 'w') as f:
            stream.dump(f)


@click.group()
def manager():
    pass


@click.command()
def worker():
    """Start task queue workers."""
    from slivka.scheduler.task_queue import TaskQueue
    queue = TaskQueue()
    queue.register_terminate_signal(2, 15)
    queue.start()


@click.command()
def scheduler():
    """Start job scheduler."""
    from slivka.scheduler.scheduler import Scheduler
    scheduler = Scheduler()
    scheduler.register_terminate_signal(2, 15)
    scheduler.start()


@click.command()
def server():
    """Start HTTP server."""
    from slivka.server.serverapp import app
    app.run(
        host=slivka.settings.SERVER_HOST,
        port=int(slivka.settings.SERVER_PORT),
        debug=bool(slivka.settings.DEBUG)
    )


@click.command()
def initdb():
    """Initialize the database."""
    from slivka.db import create_db
    create_db()


@click.command()
@click.confirmation_option(prompt="Are you sure you want to drop the database?")
def dropdb():
    """Drop the database."""
    from slivka.db import drop_db
    drop_db()


@click.command()
def shell():
    """Start an interactive shell."""
    import code
    code.interact()


manager.add_command(worker)
manager.add_command(scheduler)
manager.add_command(server)
manager.add_command(initdb)
manager.add_command(dropdb)
manager.add_command(shell)
