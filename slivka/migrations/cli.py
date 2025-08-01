from importlib import import_module

import click

_migration_warning_prompt = (
    "Migrations are potentially destructive operations!\n"
    "Consider backing up the database, slivka project and job files.\n"
    "Do you want to continue?"
)

migration_modules = [
    import_module(".migration_1", __package__),
    import_module(".migration_2_tz_aware_datetimes", __package__),
]
migrations = [
    (mod.name, mod.from_versions, mod.to_version, command)
    for mod in migration_modules
    for command in (
        getattr(mod, name) for name in dir(mod)
        if isinstance(getattr(mod, name), click.Command)
    )
]


@click.group('migration')
def migration_cli():
    pass


for _name, _from_ver, _to_ver, command in migrations:
    migration_cli.add_command(command)
