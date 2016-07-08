import os

import click
import jinja2
import pkg_resources

import pybioas.utils


@click.command()
@click.argument("name")
@click.option("--examples/--no-examples", default=True, is_flag=True,
              help="Add examples to the project.")
def setup(name, examples):
    project_dir = os.path.abspath(os.path.join(os.getcwd(), name))
    if os.path.isdir(project_dir):
        click.confirm(
            "Directory already exist. Do you want to set the project here?",
            abort=True
        )
    os.makedirs(project_dir, exist_ok=True)

    # copy pybioas.py template
    with open(os.path.join(project_dir, "manage.py"), "wb") as f:
        f.write(pkg_resources.resource_string(
            "pybioas", "data/template/manage.py.jinja2"
        ))

    # copy settings.py template
    settings_tpl = jinja2.Template(
        pkg_resources.resource_string(
            "pybioas", "data/template/settings.py.jinja2"
        ).decode()
    )
    tpl_stream = settings_tpl.stream(
        secret_key=os.urandom(32),
        example=examples
    )
    with open(os.path.join(project_dir, "settings.py"), "w") as f:
        tpl_stream.dump(f)

    # copy services.ini template
    services_tpl = jinja2.Template(
        pkg_resources.resource_string(
            "pybioas", "data/template/services.ini.jinja2"
        ).decode()
    )
    tpl_stream = services_tpl.stream(
        project_root=project_dir, example=examples
    )
    with open(os.path.join(project_dir, "services.ini"), "w") as f:
        tpl_stream.dump(f)

    if examples:
        # copy example data
        pybioas.utils.copytree(
            pkg_resources.resource_filename('pybioas', "data/examples"),
            os.path.join(project_dir)
        )


@click.group()
def admin():
    pass


@click.command()
def worker():
    """Starts task queue worker."""
    from pybioas.scheduler.task_queue.worker import start_worker
    start_worker()


@click.command()
def scheduler():
    """Starts job scheduler."""
    from pybioas.scheduler.scheduler import start_scheduler
    start_scheduler()


@click.command()
def server():
    """Starts server."""
    from pybioas.server.forms import init_forms
    from pybioas.server.serverapp import app

    init_forms(pybioas.settings.SERVICE_INI)
    app.run(host='localhost', port=8080, debug=True)


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


admin.add_command(worker)
admin.add_command(scheduler)
admin.add_command(server)
admin.add_command(initdb)
admin.add_command(dropdb)
