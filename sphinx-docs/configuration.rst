Starting the project
====================

In order to create a new Slivka project navigate to the folder where you want
to set-up your project and use the executable created during the installation.
::

   slivka-setup <name>

Replacing ``<name>`` with the name of the project you create.
If the executable cannot be accessed (e.g. it is not in the PATH), you
can equivalently run the slivka module with ::

   python -m slivka <name>

It will create a new folder ``<name>`` and copy three core files to it and
sample service with its configuration. The three core files of the project are:

:manage.py:
  a main executable script which configures Slivka and runs its components.
:settings.py:
  a settings Python module which contains project constants.
:service.ini:
  manages services execution and points to configuration files

All three files are unicode text files and can be edited with any text editor.


Settings file
-------------

``settings.py`` is a Python module file containing several constants which
are used over the entire application. Since it's a python code which gets
imported and executed every time Slivka is started, you can place some
initialization scripts in here.
Several constants are inserted on project creation, but you are free to add
more, keeping that only uppercase variables are considered settings variables.
Here is the list of constants created on project set-up with description.

:``BASE_DIR``:
  Must be set to the absolute location of the project folder. It tells the
  script the path all other paths are relative to. It defaults to the
  directory containing the settings file.

  .. code-block:: python

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

  You can set it to any path using ``os.path.join`` surrounded by
  ``os.path.abspath``. Relative paths should be avoided as they start at
  current work directory which may be different for each execution.
  It's recommended to leave it unchanged.

  Example:

  .. code-block:: python

    BASE_DIR = os.path.abspath(os.path.join("/", "var", "slivka"))
    # /var/slivka (Unix)
    # C:\var\slivka (Windows)

    BASE_DIR = os.path.abspath("/home/user/slivka/")
    # /home/user/slivka (Unix)
    # C:\home\user\slivka (Windows)

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

:``UPLOADS_DIR``:
  Directory where all files uploaded by users and produced by services are
  stored. It can be either an absolute path or path relative to the
  ``BASE_DIR``.

:``TASKS_DIR``:
  A folder where execution work directories will be created. Can be either
  an absolute path or path relative to the ``BASE_DIR``.

:``SERVICE_INI``:
  Path to *service.ini* file, absolute or relative to ``BASE_DIR``.

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


Services configuration
----------------------

An entry point to service configuration is put in the *service.ini* file.
The file consist of sections whose name is pun in square brackets ``[section]``
and key-value pairs mapped to each other with equality sign (=) or colon (:)
e.g. ``key = value``. More details about the structure of the file can be
found in the configparser_ documentation.

.. _configparser: https://docs.python.org/3/library/configparser.html#supported-ini-file-structure

The ``[DEFAULT]`` section is ignored by the application and can
be used to define constants i.e. project directory. These constants can be
referred using ``%(key)s`` placeholder similar to C-style formatting.
In the following example, the ``address`` field will be evaluated to
``example.com:80``

.. code-block:: ini

  [DEFAULT]
  host = example.com
  port = 80
  address = %(host)s:%(port)s

Each section (except ``[DEFAULT]``) corresponds to one service configuration.
Services can be anything ranging from a different ways to call an application
to range of different applications. The section must contain two keys:

:``config``:
  The path to the command definition file which structure is described in the
  `Command description`_ section.

:``form``:
  The path to user form definition file described in the `Form description`_
  section.

A sample configuration section of a service *Lorem* may look like this:

.. code-block:: ini

  [DEFAULT]
  root_path = /home/myself/slivka-project

  [Lorem]
  config = %(root_path)s/config/LoremConfig.yml
  form = %(root_path)/config/LoremForm.yml


Form description
----------------

Form description file specified what fields are presented to the front end user
and what field values are expected. The file should contain a single JSON
object which keys are unique form field names and values are options and
restrictions imposed on the form field values.
Each field, regardless of its type, have three option fields:

``label``:
  Human readable name of the field (required)
``description``:
  Detailed description of the fields or help text (optional)
``value``:
  `Value object`_ describing accepted field values (required)

Example of the form accepting two fields, file and file format is shown below.

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

Each value object, regardless of its type, may have three properties: ``type``,
``required``, ``default``. First, ``type``, is required and can take one of the
following values: ``int``, ``float``, ``text``, ``boolean``, ``choice`` or
``file``.
Second, ``required``, is required and specifies whether the value must be
specified for the form to be valid.
Third, ``default``, is optional and its value should match type of the field.
It's the default value of the field if user won't choose anything.
Note that specifying default value makes the field not required as default
value is used if the field is left ampty.

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
  Boolean field evaluates to true for each input value except ``"false"``,
  ``"0"``, ``"null"``, ``"no"``; otherwise, it becomes ``None``

  .. code-block:: json

    {
      "type": "boolean",
      "default": false
    }

:choice:
  In choice field only one of the available choices can be selected.

  ``choices`` : (object)
    Choices are defined as an object where property key is option name and the
    value is choice value. When the choice name is selected, it's value is
    passed to the parameter.

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
Optionally you may add ``val`` if you want to use a default value.

:``ref``:
  Corresponding field name in the form definition file. The value of the form
  field with this name will be used for this option.

:``param``:
  Template of the command option. Field value will be replaced for ``${value}``
  placeholder. i.e. ``--in ${value}``, ``-a=${value}``.
  ``${value}`` is not required and, if not given, the option will be
  passed independently of the field value.

:``val``:
  Value used if corresponding field in the form is not found or evaluates to
  ``None``. Useful when you need to specify constants i.e. output file flag.

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
interpreted as computation result, error message or log file, respectively.
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

Note, ``path`` should be used if the service is exprected to produce the file.
If command returns and this file is not present, job is considered failed.
``pattern`` should be used for multiple files and optional files when zero or
more files are expected. These paths are evaluated lazily after the job is
finished and match as many files as is present at the job completion.

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

Path to the Python class which performs selection of the configuration based on
command parameters. It has to be a valid Python import path (packages separated
with dots) accessible to the application. Folder containing Python module and
its parent folders must contain an empty *__init__.py* file to be Python
packages.
More details on limits classes is in the `Limits class`_ section.


Limits class
------------

In your project configuration you may create one of more Python modules
containing limit classes. Each class should contain methods which allows to
pick one configuration when given values passed to the form.

Limits class must extend ``slivka.scheduler.executors.JobLimits`` class
and define one class attribute ``configurations`` containing the list of
configuration names in order of evaluation.
For each configuration you should specify a method named
``limit_<configuration>`` which accepts one argument - dictionary containing
form values. Each of the methods should return ``True`` or ``False`` depending
on whether for given form values this configuration should be selected.
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
exceed 1000B. Otherwise, scheduler will refuse to start the job.

Field values can be obtained from the method argument using field name as a
dictionary key. All values are strings in the format as they are entered in the
shell command and may require conversion to other types.
