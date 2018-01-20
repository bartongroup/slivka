===============
Running the app
===============

Slivka consists of two core parts: rest http server and job scheduler.
Separation allows them to run independently of each other. In case
when the scheduler is down, server keeps collection requests and stash them,
so when the scheduler is working again it can catch up with the server.
Each component is launched using the *manage.py* script created on project
creation with additional arguments.

Additionally, you can use a simple task queue shipped with Slivka to run tasks
on the local machine without additional software installed.

To launch the project, you need to create a database file with a schema
by executing ::

  python manage.py initdb

It will create an *sqlite.db* file in the current working directory and
automatically create all required tables.

In order to delete the database, you may call ::

  python manage.py dropdb

or remove it manually fom the file system.

Next, you need to launch REST server and scheduler processes.
Server can be started with ::

  python manage.py server

Then, you can start the scheduler process with ::

  python manage.py scheduler

If you decided to use local queue to process jobs, you can run it with ::

  python manage.py worker

To stop any of these processes, send the ``INTERRUPT`` signal to it to close it
gracefully.
