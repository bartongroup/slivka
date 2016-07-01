#!usr/bin/env

import click


@click.group()
def main(): pass


@click.command()
def worker():
    from pybioas.scheduler.task_queue.worker import start_worker
    start_worker()


@click.command()
def runscheduler():
    from pybioas.scheduler.scheduler import start_scheduler
    start_scheduler()


@click.command()
def runserver():
    from pybioas.server.serverapp import app
    app.run(host='localhost', port=8080, debug=True)


@click.command()
def initdb():
    from pybioas.db import create_db
    create_db()


@click.command()
@click.confirmation_option(prompt="Are you sure you want to drop the db?")
def dropdb():
    from pybioas.db import drop_db
    drop_db()


main.add_command(worker)
main.add_command(runscheduler)
main.add_command(runserver)
main.add_command(initdb)
main.add_command(dropdb)


if __name__ == '__main__':
    main()
