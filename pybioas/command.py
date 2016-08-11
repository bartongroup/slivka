import logging.config
import os

import click
import jinja2
import pkg_resources

import pybioas.utils


@click.command()
@click.argument("name")
def setup(name):
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
            "pybioas", "data/template/manage.py.jinja2"
        ))

    # copy settings.py template
    settings_tpl = jinja2.Template(
        pkg_resources.resource_string(
            "pybioas", "data/template/settings.py.jinja2").decode())
    tpl_stream = settings_tpl.stream(secret_key=os.urandom(32))
    with open(settingspy_path, "w") as f:
        tpl_stream.dump(f)

    # copy services.ini template
    services_tpl = jinja2.Template(
        pkg_resources.resource_string(
            "pybioas", "data/template/services.ini.jinja2").decode())
    tpl_stream = services_tpl.stream(form_path=form_path, config_path=conf_path)
    with open(servicesini_path, "w") as f:
        tpl_stream.dump(f)

    # copy form description
    with open(form_path, 'wb') as f:
        f.write(pkg_resources.resource_string(
            "pybioas", "data/template/config/pydummyForm.yml"
        ))

    # copy pydummy configuration
    conf_tpl = jinja2.Template(
        pkg_resources.resource_string(
            "pybioas", "data/template/config/pydummyConf.yml").decode())
    tpl_stream = conf_tpl.stream(pydummy_path=pydummy_path)
    with open(conf_path, 'w') as f:
        tpl_stream.dump(f)

    # copy service limits
    with open(limits_path, 'wb') as f:
        f.write(pkg_resources.resource_string(
            'pybioas', 'data/template/config/limits.py'
        ))

    with open(pydummy_path, 'wb') as f:
        f.write(pkg_resources.resource_string(
            "pybioas", "data/template/binaries/pydummy.py"
        ))


@click.group()
def admin():
    logging.config.dictConfig(pybioas.settings.LOGGER_CONF)


@click.command()
def worker():
    """Starts task queue workers."""
    from pybioas.scheduler.task_queue import TaskQueue
    queue = TaskQueue()
    queue.start()


@click.command()
def scheduler():
    """Starts job scheduler."""
    from pybioas.scheduler.scheduler import Scheduler
    sched = Scheduler()
    sched.start()


@click.command()
def server():
    """Starts server."""
    from pybioas.server.forms import init_forms
    from pybioas.server.serverapp import app

    init_forms(pybioas.settings.SERVICE_INI)
    app.run(
        host=pybioas.settings.SERVER_HOST,
        port=pybioas.settings.SERVER_PORT,
        debug=pybioas.settings.DEBUG
    )


@click.command()
def initdb():
    """Initializes the database."""
    from pybioas.db import create_db
    create_db()


@click.command()
@click.confirmation_option(prompt="Are you sure you want to drop the db?")
def dropdb():
    """Drops the database."""
    from pybioas.db import drop_db
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
