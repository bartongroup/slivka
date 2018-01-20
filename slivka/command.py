"""Entry points for command line interface.

This module provides a collection of functions which are called directly from
the command line interface. Each function corresponds to the command with the
same name as the function, which is passed as a first parameter to the script
call. Additionally, some of the functions process additional arguments
usually specified just after the command name.
"""

import logging.config
import os
import stat

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

    Calling this fuction is a default behaviuor when a slivka module is
    executed.

    :param name: name of the project folder
    """
    project_dir = os.path.abspath(os.path.join(os.getcwd(), name))
    managepy_path = os.path.join(project_dir, "manage.py")
    settingspy_path = os.path.join(project_dir, "settings.py")
    servicesini_path = os.path.join(project_dir, "services.ini")
    form_path = os.path.join(project_dir, 'config', 'pydummyForm.yml')
    conf_path = os.path.join(project_dir, 'config', 'pydummyConf.yml')
    limits_path = os.path.join(project_dir, 'config', 'limits.py')
    pydummy_path = os.path.join(project_dir, 'bin', 'pydummy.py')

    if os.path.isdir(project_dir):
        click.confirm(
            "Directory already exist. Do you want to set the project here?",
            abort=True
        )
    os.makedirs(project_dir, exist_ok=True)
    os.mkdir(os.path.dirname(form_path))
    os.mkdir(os.path.dirname(pydummy_path))

    # copy manage.py template
    with open(managepy_path, "wb") as f:
        f.write(pkg_resources.resource_string(
            "slivka", "data/template/manage.py.jinja2"
        ))
    os.chmod(managepy_path, stat.S_IRWXU)

    # copy settings.py template
    settings_tpl = jinja2.Template(
        pkg_resources.resource_string(
            "slivka", "data/template/settings.py.jinja2").decode())
    tpl_stream = settings_tpl.stream(secret_key=os.urandom(32))
    with open(settingspy_path, "w") as f:
        tpl_stream.dump(f)

    # copy services.ini template
    services_tpl = jinja2.Template(
        pkg_resources.resource_string(
            "slivka", "data/template/services.ini.jinja2").decode())
    tpl_stream = services_tpl.stream(form_path=form_path, config_path=conf_path)
    with open(servicesini_path, "w") as f:
        tpl_stream.dump(f)

    # copy form description
    with open(form_path, 'wb') as f:
        f.write(pkg_resources.resource_string(
            "slivka", "data/template/config/pydummyForm.yml"
        ))

    # copy pydummy configuration
    conf_tpl = jinja2.Template(
        pkg_resources.resource_string(
            "slivka", "data/template/config/pydummyConf.yml").decode())
    tpl_stream = conf_tpl.stream(pydummy_path=pydummy_path)
    with open(conf_path, 'w') as f:
        tpl_stream.dump(f)

    # copy service limits
    with open(limits_path, 'wb') as f:
        f.write(pkg_resources.resource_string(
            'slivka', 'data/template/config/limits.py'
        ))
    open(os.path.join(os.path.dirname(limits_path), '__init__.py'), 'w').close()

    with open(pydummy_path, 'wb') as f:
        f.write(pkg_resources.resource_string(
            "slivka", "data/template/binaries/pydummy.py"
        ))
    os.chmod(pydummy_path, stat.S_IRWXU)


@click.group()
def admin():
    """Initialize logger.

    Function groups all command making sure that the logger is always
    initialized before the program is started.
    """
    logging.config.dictConfig(slivka.settings.LOGGER_CONF)


@click.command()
def worker():
    """Starts task queue workers."""
    from slivka.scheduler.task_queue import TaskQueue
    queue = TaskQueue()
    queue.start()


@click.command()
def scheduler():
    """Starts job scheduler."""
    from slivka.scheduler.scheduler import Scheduler
    sched = Scheduler()
    sched.start()


@click.command()
def server():
    """Starts HTTP server."""
    from slivka.server.forms import init_forms
    from slivka.server.serverapp import app

    init_forms(slivka.settings.SERVICE_INI)
    app.config.update(
        DEBUG=True,
        MEDIA_DIR=slivka.settings.MEDIA_DIR,
        SECRET_KEY=slivka.settings.SECRET_KEY
    )
    app.run(
        host=slivka.settings.SERVER_HOST,
        port=slivka.settings.SERVER_PORT,
        debug=slivka.settings.DEBUG
    )


@click.command()
def initdb():
    """Initializes the database."""
    from slivka.db import create_db
    create_db()


@click.command()
@click.confirmation_option(prompt="Are you sure you want to drop the database?")
def dropdb():
    """Drops the database."""
    from slivka.db import drop_db
    drop_db()


@click.command()
def shell():
    """Starts python interactive shell with project configuration"""
    import code
    code.interact()


admin.add_command(worker)
admin.add_command(scheduler)
admin.add_command(server)
admin.add_command(initdb)
admin.add_command(dropdb)
admin.add_command(shell)
