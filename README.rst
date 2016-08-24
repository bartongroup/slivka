#####################
PyBioAS Documentation
#####################

PyBioAS is a server application for Python intended for easy and flexible
configuration of REST API for various web services. The server is based on
Flask_ microframework and SQLAlchemy_. The scheduler uses native Python
queuing mechanism and sqlite_ database.

.. _Flask: https://github.com/pallets/flask
.. _SQLAlchemy: https://github.com/zzzeek/sqlalchemy
.. _sqlite: https://www.sqlite.org/


=============================
Installation and requirements
=============================

Installation requires Python 3.3+ (recommended version 3.5).
Additional requirements, which will be downloaded and installed automatically,
are:

- click (6.6)
- Flask (0.11.1)
- itsdangerous (0.24)
- Jinja2 (2.8)
- jsonschema (2.5.1)
- MarkupSafe (0.23)
- PyYAML (3.11)
- SQLAlchemy (1.0.13)
- Werkzeug (0.11.10)

It's recommended to install PyBioAS inside a virtual environment.
Get virtualenv with ``pip install virtualenv`` (on some Linux distributions
you may need to install ``apt-get install python-virtualenv``).
Run ``virtualenv env``, wait for it to create a new environment in ``env``
directory and activate using ``source env/bin/activate`` on Unix/OS X or
``env\Scripts\activate.bat`` on Windows. More information about the package
can be found in `virtualenv documentation`_.

.. _`virtualenv documentation`: https://virtualenv.pypa.io/en/stable/

To install PyBioAS download PyBioAS zip or tar archive and run
``pip install PyBioAS-<version>.zip``. Setuptools and all requirements
will be downloaded if not present, so internet connection is required
during the installation.


======================
Setting up the project
======================

Navigate to the folder where you want to create your project and run: ::

  pybioas-setup <name> [--examples/--no-examples]

It will create a new folder ``<name>`` and upload three files to it:
*settings.py*, *manage.py* and *services.ini*. You usually need to modify
only the last one. ``--examples`` flag tells whether to include sample
service and its configuration. By default examples are added to the project.

:manage.py:
  a main executable script which configures PyBioAS and runs its components.
:settings.py:
  a settings python module which contains project constants.
:service.ini:
  manages services execution and points to configuration files


Configuring settings
--------------------

``settings.py`` is a Python module file which provides execution constants:

:``BASE_DIR``:
  Must be set to the absolute location of the project folder. It tells the
  script the path all other paths are relative to. It defaults to the
  directory containing the settings file.

  .. code-block:: python

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

  You can set it to any path using ``os.path.join`` wrapped in ``os.path.abspath``.
  Relative paths should be avoided as they start at current work directory
  which may be different for each execution.
  It's recommended to leave it unchanged.

  Example:

  .. code-block:: python

    BASE_DIR = os.path.abspath(os.path.join("/", "var", "pybioas"))
    # /var/pybioas (Unix)
    # C:\var\pybioas (Windows)

    BASE_DIR = os.path.abspath("/home/user/pybioas/")
    # /home/user/pybioas (Unix)
    # C:\home\user\pybioas (Windows)

    BASE_DIR = os.path.abspath("C:\\Windows\\system32")
    # C:\Windows\system32 (Windows)
    # (some nasty output on Linux)

:``SECRET_KEY``:
  A string of bytes used for signatures. Changing this key will invalidate all
  identifier signatures. Please keep this key secret.

  The key can be set to either bytes or unicode characters.

  .. code-block:: python

    SECRET_KEY = b'\x00\x01\x02\x03'

    SECRET_KEY = "Lorem ipsum dolor sit amet"

:``MEDIA_DIR``:
  Directory where all files uploaded by users and produced by services are
  stored. It can be either an absolute path or path relative to the
  ``BASE_DIR``.

:``WORK_DIR``:
  A folder where execution work directories will be created. Can be either
  an absolute path or path relative to the ``BASE_DIR``.

:``SERVICE_INI``:
  Path to *service.ini* file, absolute or relative to ``BASE_DIR``.

:``SERVICES``:
  List of services available on your platform.
  It consists of case-sensitive names of the installed services.

  Example:

  .. code-block:: python

    SERVICES = ["Lorem", "Ipsum", "Dolor", "Sit", "Amet"]


Configuring services
--------------------

A general service configuration is contained in the *service.ini* file.
The first section, called ``[DEFAULT]``, is ignored by the application and can
be used to define constants like project directory. These constants can be
referred using ``%(key)s`` placeholder.

``address`` field in the following example

.. code-block:: ini

  [DEFAULT]
  host = example.com
  port = 80
  address = %(host)s:%(port)s

will be evaluated to ``example.com:80``

Each section (except ``[DEFAULT]``) corresponds to one service configuration
defined in the services list in the *settings.py* file.
The section must contain two keys:

:``command_file``:
  The path to the command definition file described in the section
  `Command description`_.

:``bin``:
  Executable command e.g. ``java dummyFile`` or ``bin\runme.bat``

Optional keys are environment variables which will be set for each command
execution. Each key must start with ``env.`` followed by the variable name
to be considered the environment variable.
Every variable set will **replace** existing system variable.

A sample configuration section of service Lorem may look like this:

.. code-block:: ini

  [Lorem]
  command_file = %(root_path)s/conf/LoremConfig.yml
  bin = python %(root_path)s/scripts/lorem.py
  env.PATH = /home/lorem_env/bin/
  env.PYTHONPATH = /home/myPythonLib/


Command description
-------------------

Command description files tell the application how to communicate with the script.
They describe what command options are expected from the user, what the
values are confined to and outputs which will be produced and sent back to the
user.

The file should be written using either YAML or JSON syntax and should
follow structure described below. JSON schema of the command description
is defined in the `Command Description Schema`_ file.

The root object must have exactly two properties: ``options`` which is the
list of `option objects <#option-object>`__ and ``outputs`` which is the list
of `output objects <#output-object>`__.

.. code-block:: json

  {
    "options": [],
    "outputs": []
  }

.. _Command Description Schema: pybioas/data/utils/CommandDescriptionSchema.json

Option object
^^^^^^^^^^^^^

Each option object must have properties ``name``, ``label``, ``parameter`` and
``value`` and the optional property ``description``

:``name``:
  Name of the field which is used for identification and as a request parameter.
  It should contain between 1 and 16 alphanumeric characters and be unique for
  each field.

:``label``:
  Human readable field name which will be displayed to the front-end user.
  The purpose of this value is to help identify the field.

:``description``:
  Optional long description of the field.

:``parameter``:
  Template of the command option. Field value will be replaced for ``${value}``
  placeholder. i.e. ``--in ${value}``, ``-a=${value}``.
  ``${value}`` is not required and, if not given, the option will be independent
  of the field value.

:``value``:
  Details about what value is expected. Value objects are described in more
  details in the `Value object`_ section.

Example:

.. code-block:: json

  {
    "name": "alpha",
    "label": "Alpha",
    "description": "Text assigned to the first alphabet letter.",
    "parameter": "-a ${value}",
    "value": {
      "type": "text"
    }
  }

Value object
^^^^^^^^^^^^

Each value object regardless of its type have two properties. First,
``type``, is required and can take one of the following values: ``integer``,
``decimal``, ``text``, ``boolean``, ``choice`` or ``file``. Second one,
``default``, is optional and its value should match type of the field.

All other properties are optional and they are specific for different types.

:integer:
  ``min`` : (int)
    Inclusive minimum value, unbound if not present
  ``max`` : (int)
    Inclusive maximum value, unbound if not present

  .. code-block:: json

    {
      "type": "integer",
      "min": 0,
      "max": 10,
      "default": 5
    }

:decimal:
  ``min`` : (float)
    Minimum value, unbound if not present
  ``max`` : (float)
    Maximum value, unbound if not present
  ``minExclusive`` : (boolean)
    Is minimum exclusive?
  ``maxExclusive`` : (boolean)
    Is maximum exclusive?

  .. code-block:: json

    {
      "type": "decimal",
      "min": -4.0,
      "minExclusive": false,
      "max": 4.0,
      "maxExlusive": true,
      "default": 0
    }

:text:
  ``minLength`` : (int)
    Minimum length of the text, minimum 0.
  ``maxLength`` : (int)
    Maximum length of the text, minimum 0.

  .. code-block:: json

    {
      "type": "text",
      "minLength": 1,
      "maxLength": 8
    }

:boolean:
  ``value`` : (string)
    Value assigned to the field if true. Otherwise, an empty string is set.
    For boolean flags it's recommended to set parameter to ``${value}``
    and boolean value to flag. e.g. ``--flag``

  .. code-block:: json

    {
      "type": "boolean",
      "value": "--flag",
      "default": false
    }

:choice:
  In choice field only one of the available choices can be selected.

  ``choices`` : (object)
    Choices are defined as an object where property key is option and the
    value is choice value. When the choice is selected, it's value is passed
    to the parameter.

  .. code-block:: json

    {
      "type": "choice",
      "choices": {
        "Alpha": "--alpha",
        "Beta": "--beta",
        "Gamma": "--gamma"
      },
      "default": "--alpha"
    }

:file:
  ``mimetype`` : (string)
    Accepted mime type of the file.
  ``extension`` : (string)
    Accepted file extensions (without leading dot)
  ``maxSize`` : (string)
    Maximum file size represented as a number and units e.g. ``5B``, ``2GB``.
    Number must be an integer and allowed units are: B, KB, MB, GB or TB.

  .. code-block:: json

    {
      "type": "file",
      "mimetype": "text/plain",
      "extension": "md",
      "maxSize": "10KB"
    }


Output object
^^^^^^^^^^^^^

Output objects describe possible outputs of the command execution.
They are defined by the output type and the output method.
Each output object should have ``type`` property which takes one of the values:
``result``, ``error`` or ``log`` which indicates whether the output should be
interpreted as computation result, error message or log, respectively.
``method`` property, which is one of: ``stdout``, ``stderr`` or ``file``,
defines how the output can be retrieved. Values indicate standard output
stream, standard error stream or file.
Additionally, if the output method is set to ``file``, exactly one of the
following properties must be provided

:``filename``:
  A name with relative path to the output file.

:``parameter``:
  Command line option template which will be used to define the output file
  name. File name is substituted for ``${value}`` placeholder.
  e.g. ``--out ${value}``

:``pattern``:
  Regular expression which should match all output files.
  May be used to specify the folder with output files.

Example of the list of outputs:

.. code-block:: json

  [
    {
      "type": "error",
      "method": "stderr"
    },
    {
      "type": "log",
      "method": "file",
      "filename": "log.txt"
    },
    {
      "type": "result",
      "method": "file",
      "pattern": "/build/.+\\.o"
    },
    {
      "type": "result",
      "method": "stdout"
    }
  ]


===============
Running the app
===============

PyBioAS consists of three main parts: http server, job scheduler and
local execution queue. Separation allows them to run independently e.g.
when the scheduler is down, server keeps collection requests and stash them,
so when the scheduler is working again it can catch up with the server.
Each component is launched using *manage.py* script with additional arguments.

First of all, you need to create a database file and add a schema executing ::

  python manage.py initdb

It will create a *sqlite.db* file in the current working directory.

In order to delete the file, you may call ::

  python manage.py dropdb

or remove it manually fom the file system.

Next, you need to launch three processes for each module. Http server is
launched with ::

  python manage.py server

Then, you can start the worker process with ::

  python manage.py worker

and scheduler ::

  python manage.py scheduler

To stop the process, send the ``SIG_TERM`` or ``SIG_KILL`` signal to that
process.
