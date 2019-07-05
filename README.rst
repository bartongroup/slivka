####################
Slivka Documentation
####################

Slivka is a server application for Python intended for easy and flexible
configuration of REST API for various web services. The server is based on
Flask_ microframework and SQLAlchemy_. The scheduler uses native Python
queuing mechanism and sqlite_ database. More information can be found
in the documentation_.

.. _Flask: https://github.com/pallets/flask
.. _SQLAlchemy: https://github.com/zzzeek/sqlalchemy
.. _sqlite: https://www.sqlite.org/
.. _documentation: http://warownia1.github.io/Slivka/


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

It's recommended to install Slivka inside a virtual environment.
Get virtualenv with ``pip install virtualenv`` (on some Linux distributions
you may need to install ``apt-get install python-virtualenv``).
Run ``virtualenv env``, wait for it to create a new environment in ``env``
directory and activate using ``source env/bin/activate`` on Unix/OS X or
``env\Scripts\activate.bat`` on Windows. More information about the package
can be found in `virtualenv documentation`_.

.. _`virtualenv documentation`: https://virtualenv.pypa.io/en/stable/

To install Slivka download Slivka zip or tar archive and run
``pip install Slivka-<version>.zip``. Setuptools and all requirements
will be downloaded if not present, so internet connection is required
during the installation.


======================
Setting up the project
======================

Navigate to the folder where you want to create your project and run: ::

  slivka-setup <name>

It will create a new folder ``<name>`` and upload three core files to it:
*settings.yml*, *manage.py* and *configurations/services.ini*.
You usually need to modify only the last one. Slivka will also include sample
service and its configuration.

:manage.py:
  a main executable script which configures Slivka and runs its components.
:settings.yml:
  a yaml file containing project constants.
:services.ini:
  manages services execution and points to configuration files


Configuring settings
--------------------

``settings.yml`` is a yaml file which provides all runtime constants.
The data is represented as key-value pairs using yaml format.
The following fields are required for proper operation:

:``BASE_DIR``:
  Must point to the location of the project folder (relative to the
  ``manage.py`` script or absolute path). It defines the path which all other
  paths are relative to. It defaults to the current working directory.

  .. code-block:: python

    BASE_DIR: <path-to-projet-directory>

  Relative paths should be avoided as they start at current work directory
  which may be different for each run. It's recommended to leave it unchanged.

  Example:

  .. code-block:: python

    BASE_DIR: /var/slivka
    # /var/slivka (Unix)
    # C:\var\slivka (Windows)

    BASE_DIR: /home/user/slivka/
    # /home/user/slivka (Unix)
    # C:\home\user\slivka (Windows)

    BASE_DIR: C:\\Windows\\system32
    # C:\Windows\system32 (Windows)
    # (some nasty output on Linux)

:``SECRET_KEY``:
  A string of characters used for signatures. Changing this key will invalidate
  all identifier signatures. Please keep this key secret and random.

  The key can be set to either bytes or unicode characters.

  .. code-block:: python

    SECRET_KEY : "Lorem ipsum dolor sit amet"

:``UPLOADS_DIR``:
  Directory where all files uploaded by users and produced by services are
  stored. It can be either an absolute path or path relative to the
  ``BASE_DIR``.

:``TASKS_DIR``:
  A folder where execution work directories will be created. Can be either
  an absolute path or path relative to the ``BASE_DIR``.

:``SERVICES_INI``:
  Path to *services.ini* file, absolute or relative to ``BASE_DIR``.

:``LOG_DIR``:
  Path to directory where log files will be stored. Can be either absolute
  or relative to ``BASE__DIR``.

:``QUEUE_HOST``:
  Address where the local queue is listening on. It's highly recommended to use
  localhost, as accepting connection from outside may be a security risk.

:``QUEUE_PORT``:
  Port which local queue is listening to new connections on. It must not
  collide with any commonly used ports and must be less than 65535.
  It's recommended to pick value between 1000 and 10000.

:``SERVER_HOST``:
  Address at which the server accepts connections. You should use your
  broadcast address or ``"0.0.0.0"`` to accept all connections.

:``SERVER_PORT``:
  Port used for listening to REST requests. You might use one of the common
  HTTP ports e.g. 8000, 8080 or 8888

:``DEBUG``:
  Flag indicating whether debug mode should be enabled. Debug mode should not
  be used in production.


Configuring services
--------------------

A general service configuration is contained in the
*configurations/services.ini* file. Sections are names enclosed in the square
brackets. Key-value pars are separated with a colon.
The ``[DEFAULT]`` section is ignored by the application and can
be used to define constants i.e. project directory. These constants can be
referred later using ``%(key)s`` placeholder.

Example: ``address`` field in

.. code-block:: ini

  [DEFAULT]
  host = example.com
  port = 80
  address = %(host)s:%(port)s

will be evaluated to ``example.com:80``

Each section (except ``[DEFAULT]``) corresponds to one service configuration
and must contain two keys:

:``config``:
  The path to the command definition file described in the section
  `Command description`_.

:``form``:
  The path to user form definition file descriped in the section
  `Form description`_.

A sample configuration section of service Lorem having two files
``LoremConfig.yml`` and ``LoremForm.yml`` respectively could be:

.. code-block:: ini

  [DEFAULT]
  root_path: /home/slivka/my-project

  [Lorem]
  config: %(root_path)s/config/LoremConfig.yml
  formL %(root_path)/config/LoremForm.yml


Form description
----------------

Form description file specified what fields are presented to the front end user
and what values are expected. File should contain a json or yaml object whose
keys are fields names and values are detailed specifications of the fields.
Field specification object has three fields:

``label``:
  Human readable name of the field (required)
``description``:
  Detailed description of the fields or help text (optional)
``value``:
  `Value object`_ description of accepted values (required)

.. code-block:: json

  {
    "input": {
      "label": "Input file",
      "description": "Json or Yaml file containing data to be parsed",
      "value": {
        "type": "file",
        "maxSize": "2KB",
        "required": true
      }
    },
    "format": {
      "label": "File format",
      "value": {
        "type": "choice",
        "choices": {
          "JSON": "json",
          "YAML": "yaml",
          "other": "other"
        },
        "required": false,
        "default": "json"
      }
    }
  }

Value object
^^^^^^^^^^^^

Each value object regardless of its type have three properties: ``type``,
``required``, ``default``. First, ``type``, is required and can take one of the
following values: ``int``, ``float``, ``text``, ``boolean``, ``choice`` or
``file``.
Second, ``required``, is required and specifies whether the value must be
specified for the form to be valid.
Third, ``default``, is optional and its value should match type of the field.
It's the default value of the field if user won't choose anything.
Note that specifying default value makes the field not required as default is
user for no input.

All other properties are optional and they are specific for different types.

:int:
  ``min`` : (int)
    Inclusive minimum value, unbound if not present
  ``max`` : (int)
    Inclusive maximum value, unbound if not present

  .. code-block:: json

    {
      "required": true,
      "type": "int",
      "min": 0,
      "max": 10,
      "default": 5
    }

:float:
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
      "type": "float",
      "min": -4.0,
      "minExclusive": false,
      "max": 4.5,
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
  Boolean field evaluates to true for each value except ``"false"``, ``"0"``,
  ``"null"``, ``"no"``; otherwise, it becomes `None`

  .. code-block:: json

    {
      "type": "boolean",
      "default": false
    }

:choice:
  In choice field only one of the available choices can be selected.

  ``choices`` : (object)
    Choices are defined as an object where property key is option name and the
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
      "default": "Alpha"
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


Command description
-------------------

Command description files tell the application how to communicate with the
script and how to submit it to the queue.
The file should be written using either YAML or JSON syntax and should
follow structure described below.

The root object must have the following properties: ``options`` which is the
list of `Option objects`_, ``result`` which is the list
of `Result objects`_, ``configurations`` which is the
map of configuration names and parameters described in `Configurations`_ and
``limits`` which specifies the importable Python class providing configuration
selection.

Option objects
^^^^^^^^^^^^^^

Each option object must have properties ``ref`` and ``param``.
Optionally you may add ``val`` if you want to use default value.

:``ref``:
  Corresponding field name in the form definition file. The value of the form
  field with this name will be used for this option.

:``param``:
  Template of the command option. Field value will be replaced for ``${value}``
  placeholder. i.e. ``--in ${value}``, ``-a=${value}``.
  ``${value}`` is not required and, if not given, the option will be independent
  of the field value.

:``val``:
  Value used if corresponding field in the form is not found or evaluates to
  ``None``. Useful when you need to specify constants such as output file flag.

Example:

.. code-block:: json

  {
    "options": [
      {
        "ref": "message",
        "param": "-m $value"
      },
      {
        "ref": "format",
        "param": "--format=$value"
      },
      {
        "ref": "output",
        "param": "-o $value",
        "val": "output_file.o"
      }
    ]
  }

Result objects
^^^^^^^^^^^^^^

Result objects describe possible outputs of the command execution.
Each output object should have ``type`` property which takes one of the values:
``result``, ``error`` or ``log`` which indicates whether the output should be
interpreted as computation result, error message or log, respectively.
``method`` property defines how the output can be retrieved.
The only allowed value is ``file`` which indicates that the content is stored
in the file.
If the output method is set to ``file``, exactly one of the
following properties must be provided

:``path``:
  A path to the output file relative to the current working directory.

:``pattern``:
  Regular expression used to match output files.
  May be used to specify the folder with output files or data split between
  multiple files.

Note, ``path`` should be used if file must be provided by the service.
If command returns and this file is not present, job is considered as failed.
``pattern`` should be used for multiple files and optional files when zero or
more files are expected. These paths are evaluated lazily after the job is
finished and match as many files as is present at that time.

Example of the list of outputs:

.. code-block:: json

  {
    "result": [
      {
        "type": "result",
        "method": "file",
        "pattern": "/build/.+\\.o"
      },
      {
        "type": "result",
        "method": "file",
        "path": "file.out"
      },
      {
        "type": "error",
        "method": "file",
        "pattern": "error\\.log"
      },
      {
        "type": "log",
        "method": "file",
        "path": "output.log"
      }
    ]
  }

Configurations
^^^^^^^^^^^^^^

Each configuration describes how the command will be dispatched to the queue.
It can be either local queue or Sun Grid Engine accessible on the machine.
Each key in the ``configuration`` object represents configuration name which
can be referenced in the limits module.

Values should be objects with following properties:

:``execClass``:
  Class of the executor used to start the job with given configuration.
  Available values are ``LocalExec`` for local queue manager provided with
  Slivka, ``ShellExec`` which simply spawns a new process (only recommended
  for very short jobs which takes milliseconds to complete) and
  ``GridEngineExec`` which sends the job to Sun Grid Engine.

:``bin``:
  Command or path to executable binary which will be executed with the queue.
  Command is passed as it is to the shell, so keep correct escaping and
  quotation.

:``queueArgs``:
  List of arguments passed directly to the queue command. It's optional and
  is applicable to several execution environments only.

Example:

.. code-block:: json

  {
    "configurations": {
      "local": {
        "execClass": "LocalExec",
        "bin": "python \"/var/slivka-project/binaries/pydummy.py\""
      },
      "cluster": {
        "execClass": "GridEngineExec",
        "bin": "/var/slivka-project/binaries/pydummy.py",
        "queueArgs": [
          "-v",
          "PATH=/local/python-envs/slivka/bin"
        ]
      }
    }
  }

Limits
^^^^^^

Path to Python class which performs selection of the configuration based on
command parameters. It has to be a valid Python import path (packages separated
with dots) accessible to the application. Folder containing Python module and
its parent folders must contain an empty *__init__.py* file to be Python
packages.
More details on limits classes in the `Limits class`_ section.


Limits class
------------

In your project configuration you may create one of more Python modules
containing limit classes. Each class should contain methods which allows to
pick one configuration when given values passed to the form.

Limits class must extend ``slivka.scheduler.executors.JobLimits`` class
and define one class attribute ``configurations`` containing the list of
configuration names.
For each configuration you should specify a method ``limit_<configuration>``
which accepts one argument - dictionary containing form values.
Each of the methods should return ``True`` or ``False`` depending on whether for
given form values this configuration should be selected.
Limits are evaluated in the order specified in the ``configurations`` list
and first one which returns ``True`` is picked.
You may also need to define ``setup`` method for expensive operations.
``setup`` is called before all limit methods and can be used to prepare some
variables beforehand and store them as attributes of ``self``.

Let's look at the example of dummy json/yaml reader.

.. code-block:: python

  import os

  from slivka.scheduler.executors import JobLimits

  class MyLimits(JobLimits):

      configurations = ['first_conf', 'second_conf']

      def setup(self, values):
          input_file = values['input']
          statinfo = os.stat(input_file)
          self.input_file_size = statinfo.st_size

      def limit_first_conf(self, values):
          if values['format'] == 'json' and self.input_file_size < 100:
              return True
          if values['format'] == 'yaml' and self.input_file_size < 20:
              return True
          return False

      def limit_second_conf(self, values):
          if self.input_file_size < 1000:
              return True
          else:
              return False

First, inside ``setup`` method, it retrieves input file path, checks its size
in bytes and stores the value in the ``input_file_size`` property.
Next, it checks criteria for first configuration which are: less than 100B
json file or less than 20B yaml file. If they are not met, refuse to use this
configuration and jump to the next in the list.
Second configuration, on the other hand, is executed if the file size does not
exceed 1000B. Otherwise, scheduler refuses to start the job.

Field values can be obtained from the method argument using field name as a
dictionary key. All values are strings in the format as they are entered in the
shell command and may require conversion to other types.


===============
Running the app
===============

Slivka consists of two core parts: rest http server and job scheduler.
Separation allows them to run independently of each other. In case
when the scheduler is down, server keeps collection requests and stash them,
so when the scheduler is working again it can catch up with the server.
Each component is launched using *manage.py* script with additional arguments.

Additionally, you can use simple task queue added to Slivka to run tasks
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
