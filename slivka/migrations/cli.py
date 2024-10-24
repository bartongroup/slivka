import os
from importlib import import_module

import click

_migration_warning_prompt = (
    "Migration is a potentially destructive operation!\n"
    "Consider backing up the database, slivka project and job files.\n"
    "Do you want to continue?")


@click.command()
@click.confirmation_option(prompt=_migration_warning_prompt)
def migrate():
    import slivka.conf
    home = os.getenv("SLIVKA_HOME", os.getcwd())
    os.environ["SLIVKA_HOME"] = os.path.abspath(home)
    project_version = slivka.conf.settings.version
    migrations = [
        import_module(".migration_1", __package__)
    ]
    migrations = [
        m for m in migrations if project_version in m.from_versions
    ]
    migrations.sort(key=lambda m: m.to_version)
    for migration in migrations:
        click.echo(f"Applying migration: {migration.name}")
        migration.apply()
