slivka
######

Submodules
==========

slivka.command
--------------

.. automodule:: slivka.command

.. py:function:: setup(name)

    Setup a new project in the current working directory.

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

.. py:function:: admin()

    Admin commands group.

    Function groups all command and makes sure that the logger is always
    initialized before the program is started.

.. py:function:: worker()

    Start task queue workers.

.. py:function:: scheduler()

    Start job scheduler.

.. py:function:: server()

    Starts HTTP server.

.. py:function:: initdb()

    Initialise the database.

.. py:function:: dropdb()

    Delete the database

.. py:function:: shell()

    Initialize project configuration and start python shell.

slivka.config
-------------

.. automodule:: slivka.config
    :members:


slivka.utils
------------

.. automodule:: slivka.utils
    :members:
    :undoc-members:
    :show-inheritance:


Module contents
===============

.. automodule:: slivka
    :members:
    :undoc-members:
    :show-inheritance:
