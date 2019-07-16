============
Installation
============

------------
Requirements
------------

Installation requires Python 3.5+ (Developed and tested using Python 3.5).
Additional requirements that will be downloaded and installed automatically, include:

- click (>6.6)
- Flask (>0.11.1)
- Jinja2 (>2.8)
- jsonschema (>2.5.1)
- PyYAML (>3.11)
- SQLAlchemy (>1.0.13)

-------------------------
Installing Slivka package
-------------------------

It's recommended to install Slivka inside a virtual environment using virtualenv or conda.
You can install virtualenv by running ``pip install virtualenv`` (on some Linux distributions
you may need to install a system package via ``apt-get install python-virtualenv``).
Run ``virtualenv env``, wait for it to create a new environment in ``env``
directory and activate using ``source env/bin/activate`` on Unix/OS X or
``env\Scripts\activate.bat`` on Windows.
More information about the virtualenv package can be found in `virtualenv documentation`_.
For conda users, create a new environment using ``conda create -n slivka python=3.5``
and activate with ``conda activate slivka``.
More details can be found in `conda documentation`_.

.. _`virtualenv documentation`: https://virtualenv.pypa.io/en/stable/
.. _`conda documentation`: https://conda.io/en/latest/

In order to install Slivka download Slivka choose the suitable zip or tar archive
form the repository_ and run install inside your virtual environment with
``pip install Slivka-<version>.(zip|tar)``.
Alternatively, you can install the most recent version directly from our github
repository with ``pip install git+git://github.com/warownia1/Slivka``.
Setuptools and all other requirements will be downloaded if not present, so internet
connection is required during the installation.

.. _repository: https://github.com/warownia1/Slivka/releases

After the installation, a new executable ``slivka-setup`` will be added to your Python
scripts directory. It will be used to create new Slivka projects. Make sure that it is
available in your ``PATH``.

--------------------
Creating new project
--------------------

In order to create a new Slivka project navigate to the folder where you want
it to be set-up and run the executable created during the installation.
::

   slivka-setup <name>

Replacing ``<name>`` with the name of the new project directory that will be created.
Use ``.`` if you wish to set-up the project in the current directory.
If the executable cannot be accessed (e.g. it is not in the PATH), you
can equivalently run the slivka module with ::

   python -m slivka <name>

It will create a new folder named ``<name>`` and initialize project files in it.
Additionally, an example service and its configuration will be included.

=================
Project Structure
=================

The Slivka project exists separately from the Slivka package and contains its own set
of configurations. You can create as many project as you like with one Slivka installations.
Each project contains three core files:

:manage.py:
  The main executable script which configures Slivka and runs its components.
:settings.yml:
  A settings file which defines project-wide parameters.
:services.ini:
  A list of available services with paths to their respective configuration files.
:wsgi.py:
  Module containing a wsgi application for dedicated wsgi servers.

Additionally, you need to create configuration files for each of your services
and add them to the ``services.ini`` file.

The configuration files are unicode text files and can be edited with any text editor.
It is not advisable, however, to edit the main executable ``manage.py`` and ``wsgi.py``.

-------------
Settings file
-------------

``settings.yml`` is a yaml formatted file defining constants and parameters used
throughout the application. The parameters are case sensitive and should be written
using capital letters.

The following list shows all the parameters required by the Slivka application.

:``BASE_DIR``:
  Indicates the location of the project directory. Absolute paths are preferred.
  The location must be accessible for the user running the application.
  It tells Slivka the path to the project files and where all relative paths should start from.
  It defaults to the directory containing the ``manage.py`` file and it's recommended to leave it this way.

  Examples:

  .. code-block:: yaml

    BASE_DIR: /home/slivka/project

    BASE_DIR: C:\Users\slivka\project

:``UPLOADS_DIR``:
  Directory where all user uploaded files are stored.
  It's recommended to serve files directly from this directory.
  It can be either an absolute path or a path relative to the ``BASE_DIR``.

  Default: ``./media/uploads``

:``TASKS_DIR``:
  A folder where job working directories are created and output files are stored.
  It's recommended to serve files directly from this directory.
  Can be either an absolute path or path relative to the ``BASE_DIR``.

  Default: ``./media/tasks``

:``LOG_DIR``:
  Path to directory where log files are be stored.
  Can be either an absolute path or a path relative to the ``BASE_DIR``.

  Default: ``./logs``

:``SERVICE_INI``:
  Path to the *service.ini* file containing the list of available services.
  Can be either an absolute path or a path relative to the ``BASE_DIR``.

  Default: ``./configurations/services.ini``

:``UPLOADS_URL_PATH``:
  The URL path where the uploaded files will be available from.
  This setting enables you to set the path so the files can be served with a third-party proxy server
  e.g. Apache or Nginx.

  Default: ``/media/uploads``

:``TASKS_URL_PATH``:
  The URL path where the tasks output files will be available from.
  This setting enables you to set the path so the files can be served with a third-party proxy server
  e.g. Apache or Nginx.

:``ACCEPTED_FILE_TYPES``:
  The list of media mime-types that will be accepted by the server.
  The names can be listed using either json or yaml syntax

  Example:

  .. code-block:: yaml

    ACCEPTED_FILE_TYPES: ["text/plain", "application/json"]

  .. code-block:: yaml

    ACCEPTED_FILE_TYPES:
      - text/plain
      - application/json

:``SERVER_HOST``:
  The hostname which the server will be available at. Setting it to 0.0.0.0 makes the app accept any connection.
  If the slivka server is running behind a proxy, it's recommended to accept the connections from the proxy
  server only e.g. 127.0.0.1.

  *This parameter is ignored when running slivka server through wsgi application such as uwsgi or Gunicorn and will
  be removed in the future.*

:``SERVER_PORT``:
  Port used for listening to the requests.
  Remember that using  port number lower than 1024 may be not allowed for normal users.
  You might use one of the ports commonly used for development e.g. 8000, 8080 or 8888.

  *This parameter is ignored when running slivka server through wsgi application such as uwsgi or Gunicorn and will
  be removed in the future.*

:``QUEUE_HOST``:
  Address which the worker queue is running at.
  **It's highly recommended to use localhost, since accepting connections from the outside may be a security issue.**

:``QUEUE_PORT``:
  Port which the worker queue is accepting connections at.
  It must not collide with any commonly used ports and must be between 1024 and 65535.


----------------------
Services configuration
----------------------

The services configuration file (*configurations/services.ini* by default) contains
the collection of all available services and paths to their respective configuration files.
Each section in the file whose name written in square brackets ``[section]`` defines one service.
The section name is followed by the list of colon-separated parameter name and value pairs.

The special ``[DEFAULT]`` section is ignored by the application and can
be used to define constants i.e. project directory.
These constants can be referred to in the file using ``${key}`` placeholder.
In the following example, the ``form`` parameter of the *LoremIpsum* service evaluates to
``/home/slivka/config/Slivka_form.yml``

.. code-block:: ini

  [DEFAULT]
  configdir: /home/slivka/config
  formsuffix: _form.yml

  [LoremIpsum]
  form: ${configdir}/Slivka${formsuffix}

Each section (except for ``[DEFAULT]``) corresponds to one service configuration.
A separate service can be i.e. a different executable or a different set of options
for the same executable. Each section must contain two parameters:

:``form``:
  The path to the form definition file described in the `Form Description`_ section.

:``config``:
  The path to the run configuration file which structure is described in the
  `Run Configuration`_ section.

A sample configuration of a *LoremIpsum* service is presented in the following example:

.. code-block:: ini

  [DEFAULT]
  project_dir: /home/slivka/slivka-project

  [LoremIpsum]
  config: ${project_dir}/config/Lorem_run.yml
  form: ${project_dir}/config/Lorem_form.yml


----------------
Form Description
----------------

Form description file specified the parameters which are presented to the front end user through the web API.
It defines the name, description and expected value for each parameter.
The file should contain a single YAML object with keys representing unique field names and
`Field object`_ values.

Field Object
============

============= =============================== =================
 Field Name    Type                            Description
============= =============================== =================
label         string                          **Required.** A human readable field name.
description   string                          Detailed information about the field (help text)
value         `Value Object`_                 Value object which provides information about
                                              the expected value.
============= =============================== =================

Example of the form accepting two fields: input and format is shown below.

.. code-block:: yaml

  input:
    label: Input file
    description: JSON, YAML or XML file containing input data.
    value:
      type: file
      maxSize: 2KB
      required: yes
  format:
    label: File format
    value:
      type: choice
      choices:
        JSON: json
        YAML: yaml
        XML: xml
      required: yes
      default: JSON


Value object
============

Value objects define the content of each field. They are used for validating the user input.
The value object properties may differ depending on the field type.
However ``type``, ``required`` and ``default`` are common for every field type.

============ ========== ========================
 Field Name   Type       Description
============ ========== ========================
 type         string     **Required.** Type of the field,
                         must be: int, float, text, boolean, choice or file.
 required     boolean    **Required.** Whether the value is must be provided
 default      any        Default value, type of the parameter must match the type of the field.
============ ========== ========================


Note that supplying the default value automatically makes the field not required since the default
value is used when the field is empty.

All other properties are optional and they are specific to different field types.

Integer Value object
--------------------

============ ========= =========================
 Field Name   Type      Description
============ ========= =========================
 min          integer   Minimum value, unbound if not provided.
 max          integer   Maximum value, unbound if not provided.
============ ========= =========================

Example:

.. code-block:: yaml

  type: int
  required: true
  min: 0
  max: 10
  default: 5


Float Value object
------------------


============== ========= =========================
 Field Name     Type      Description
============== ========= =========================
 min            float     Minimum value, unbound if not provided
 max            float     Maximum value, unbound if not provided
 minExclusive   boolean   Whether the minimum should be excluded.
 maxExclusive   boolean   Whether the maximum should be excluded.
============== ========= =========================

Example:

.. code-block:: yaml

  type: float
  min: -4.0
  minExclusive: false
  max: 4.5
  maxExlusive: true
  default: 0

Text Value object
-----------------

============ ========= =========================
 Field Name  Type      Description
============ ========= =========================
 minLength   integer   The minimum length of the text.
 maxLength   integer   The maximum length of the text.
============ ========= =========================

Example:

.. code-block:: yaml

  type: text
  minLength: 1
  maxLength: 8

Boolean Value object
--------------------

============ ========= =========================
 Field Name  Type      Description
============ ========= =========================
 *(no additional properties)*
================================================

Example:

.. code-block:: yaml

  type: boolean,
  default: false

Choice Value object
-------------------

============ ======================== ==========================
 Field Name   Type                     Description
============ ======================== ==========================
 choices      object[string, string]   List of available choices.
                                       Keys should represent the values presented to the user
                                       while values the command line parameter the choice is
                                       interpreted as.
============ ======================== ==========================

Example:

.. code-block:: yaml

  type: choice
  choices:
    Alpha: --alpha
    Beta: --no-alpha
    Gamma: --third-option
  default: Alpha

File Value object
-----------------

============ ======== ===================
 Field Name   Type     Description
============ ======== ===================
 mimetype     string   Accepted content type e.g. text/plain
 maxSize      string   The maximum size of the file. The size is represented
                       with an integer and one of the allowed units: B, KB, MB, GB, TB
                       e.g. 5MB
============ ======== ===================

Example:

.. code-block:: yaml

  type: file
  mimetype: text/plain
  maxSize: 1KB


-----------------
Run configuration
-----------------

Run configuration tells Slivka how to construct the command line parameters
for the executable file and how to submit it to the queuing system along with
extra arguments and environment variables.
The file follows YAML format (JSON is also allowed) and needs to have the following
properties:

=============== ==================================== ===============
 Field name      Type                                 Description
=============== ==================================== ===============
options         array[`Argument Object`_]            List of command line arguments
                                                     this application accepts.
results         array[`Result Object`_]              List of produced output files.
configurations  map[string, `Configuration Object`_] List of possible run configurations.
limits          string                               Path to the `limiters <Limits>`_ object.
=============== ==================================== ===============

The ``options`` property defines the list of command line arguments passed to the program,
``results`` contains the list of the output files produced by the task and
``configurations`` is the list of available run configurations.
Additionally, ``limits`` property defines the path to the Python class controlling
the choice of the run configurations.

Argument Object
===============

Each argument object corresponds to a single command line parameter passed
to the executable. They will be inserted in the order they are listed in the
configuration file skipping those which have empty values.
Each argument object have two required properties ``ref`` and ``param``.
Optionally you may add ``val`` if you want to specify a default value.

============ ====== =====================
 Field Name   Type   Description
============ ====== =====================
ref          string **Required.** Name of the form field which value is passed to this parameter.
param        string **Required.** Command line parameter template.
val          string Default parameter value.
============ ====== =====================

Parameter ``ref`` defines which value from the Form will be inserted to the
command line parameter template.
The value should match one of the field names in the form description.
If you want to add a command line parameter which doesn't have a corresponding form field
it is recomment to prepend the ``ref`` name with an underscore ``_``.
Note that this parameter value will always be empty and will be skipped
unless a default value is provided into the ``val`` parameter.

The command line parameter contains a template where the value will be
substituted into and then passed as a command line argument.
The placeholder ``${value}`` is used in place of the value.
If the value is a file, then it will be converted to an absolute path to that file.
In case the executable requires its input file to be located in the current working
directory or having a specific name, it is possible to use ``${file:<name>}``
syntax substituting the file name for ``<name>``. It will create a link to the
original file in the specified location.

All placeholders which do not match ``${value}`` or ``${file:<name>}`` syntax are
treated as environment variables and are substituted in runtime if such variable
exists.

Here is an exmaple of the command line parameters definition corresponding 
to the form having ``input`` and ``format`` fields:

.. code-block:: yaml

  options:
    - ref: input
      param: -i ${file:inputfile.txt}
    - ref: format
      param: --format=${value}
    - ref: _output
      param: -o ${value}
      val: outputfile.out

If the values passed to ``input`` and ``format`` are */home/slivka/media/input.json* and
*json* respectively, the constructed command line paratemers will be 
``-i inputfile.txt --format=json -o outputfile.out`` and */home/slivka/media/input.json*
will be linked to */current/working/directory/inputfile.txt*.

Result Object
=============

Result objects describe a single file or a group of files produced by
the program. The following properties are available:

============ ====== ======================
 Field Name   Type   Description
============ ====== ======================
type         string **Required.** Type of the output that this file represents.
                    The value must be one of *output* for a regular output file,
                    *log* for standard execution logs or *error* for error logs.
path         string **Required.** Path to the output file relative to the
                    current working directory. Glob patterns are supported.
mimetype     string Media (mime) type of the file.
============ ====== ======================

The standard output and standard error are redirected to *stdout.txt* and
*stderr.txt* respectively.
The paths are evaluated lazily as the job is running and match
as many files as possible. Every defined result file is treated as optional
and its absence on job completion does not raise error.

Example:

.. code-block:: yaml

  results:
    - type: output
      path: outputfile.xml
      mimetype: application/xml
    - type: output
      path: *_aux.json
      mimetype: application/json
    - type: log
      path: stdout.txt
      mimetype: text/plain
    - type: error
      path: stderr.txt
      mimetype: text/plain


Configuration Object
====================

Each configuration describes how the command will be dispatched to the queuing system.
It can be either running a subprocess or submitting to the Local Slivka Queue or
Univa Grid Engine. More submission methods can be added by subclassing
``slivka.scheduler.runners.Runner`` class.

Each key of the ``configuration`` object represents the name of a run configuration which
will be referenced in the limits module. Each value should be a following Configuration Object:

============ =================== ==============================
 Field Name   Type                Description
============ =================== ==============================
runner       string              **Required.** Name or path to the Runner class to be used.
executable   string              **Required.** Path to executable script or binary file.
                                 ``${project_dir}`` variable is allowed and will be substituted
                                 for the absolute path to the project directory.
env          map[string, string] Additional environment variables.
queueArgs    array[string]       Additional arguments passed to the queuing system.
============ =================== ==============================

Example:

.. code-block:: yaml

  configurations:
    local:
      runner: LocalQueueRunner
      executable: bash ${project_dir}/binaries/Runnable.sh
      env:
        JAVAPATH: /usr/bin/jdk-1.8/bin
    gridengine:
      runner: GridEngineRunner
      executable: bash ${project_dir}/binaries/Runnable.sh
      env:
        JAVAPATH: /usr/bin/jdk-1.8/bin
      queueArgs: [-P, webservices, -R, y, -q, 64bit-pri.q,
                  -pe, smp, "4", -l, ram=3400M]


Limits
======

The job of limiters is to choose one of the listed configurations based on the
input data. It can filter-out long jobs and redirect them to the dedicated 
queuing system while running small jobs locally.
The value of the parameter should contain the path to the Python 
`limiter class <Creating Limiter>`_ which performs selection of the configuration
for the given service. The path must point to the class located
in the module importable for the current python interpreter.
The format of the path follows *package[.subpackages].classname* pattern.
The directory containing Python script file must be a valid python package
i.e. the directory and all its parent directories must contain an empty
*__init__.py* and should be listed in the PYTHONPATH environment variable
if not available from the current working directory.


----------------
Creating Limiter
----------------

In your project configuration you should create one or more Python modules
containing limiter classes. Each class should contain methods that allows to
pick one configuration from the configurations list based on the values
provided by the user.

The limiter class must extend ``slivka.scheduler.limits.LimitsBase`` and
if must define a class attribute ``configurations`` containing the list of
configuration names.
Additionally, for each configuration named ``<name>`` it needs to have
a method named ``limit_<name>(self, values)``.
Paramter ``values`` passed to the function contains the dictionary of
the values for the command line application.
The method must return ``True`` or ``False`` depending on whether this
run confguration can be used with these particular input values.
The configurations are tested in the order they are specified in the list
and the first confguration whose limit method returns ``True`` will be used.

Additionally, you can define ``setup(self, values)`` method which will be
run before all tests. It can be used to perform long operations and prepare
some parameters.

Example:

.. code-block:: python

  import os

  from slivka.scheduler.limits import LimitsBase

  class MyLimits(LimitsBase):

      # Use two configurations named fast and long
      configurations = ['fast', 'long']

      def setup(self, values):
          """
          Setup is run before all tests. It can perform lengthy
          file operations or data parsing.
          """
          input_file = values['input']
          statinfo = os.stat(input_file)
          self.input_file_size = statinfo.st_size

      def limit_fast(self, values):
          """
          The "fast" configuration test method.
          It accepts the input only if format is json and file is less than
          100 bytes long or xml and less than 20 bytes.
          """
          if values['format'] == 'json' and self.input_file_size < 100:
              return True
          if values['format'] == 'yaml' and self.input_file_size < 20:
              return True
          return False

      def limit_long(self, values):
          """
          The "long" configuration test method. Tried if "fast" test fails.
          It accepts any input file less than 1000 bytes,
          otherwise, the job will be rejected.
          """
          if self.input_file_size < 1000:
              return True
          else:
              return False

First, the ``setup`` method retrieves input file path, checks its size
in bytes and stores the value in the ``input_file_size`` property.
Next, the criteria for the first configuration, less than 100B
json file or less than 20B yaml file, are tested.
If they are not met, the program continues to the second configuration
which is executed if the file size does not exceed 1000B.
Otherwise, the scheduler will refuse to start the job altogether.

All values in the ``values`` dictionary are strings formatted as they
are entered into the shell and may require prior conversion to other types.

=====================
Launching the Project
=====================

Slivka consists of two core parts: RESTful HTTP server and job scheduler (dispatcher).
Their separation allows to run them independently of each other.
In situaitions when the scheduler is down, the server keeps collecting 
the requests stashing them in the database,
When the scheduler is working again it can catch up with the server
and dispatch all pending requests.
Similarly, when the server is down, the currently submitted jobs 
are unaffected and can still be processed.
Additionally, you can use a simple worker queue shipped with Slivka to run tasks
on the local machine without additional queuing system installed.

Each component is started through the *manage.py* script created in the project's
root directory.

Before the project can be started for the first time, Slivka needs to
initialize the database schema. The task is performed by running ::

  python manage.py initdb

By default it will create an *sqlite.db* file in the current working directory and
automatically create all required tables.

In order to delete the database, you may call ::

  python manage.py dropdb

or remove it manually fom the file system.

Next, you need to launch the REST server and the scheduler processes. ::

  python manage.py server

::

  python manage.py scheduler

The built-in slivka server is intended for development only.
In production, use dedicated wsgi server such as Gunicorn and provide it
a ``wsgi`` module from the project root directory e.g. ::

  gunicorn -b 0.0.0.0:8000 -w 4 -n slivka-http wsgi

If you decide to use the local queue to process jobs, you can run it with ::

  python manage.py worker

To stop any of these processes, send the ``SIGINT`` (2) "interrupt" or
``SIGTERM`` (15) "terminate" signal to the process or press **Ctrl + C**
to send ``KeyboardInterrupt`` to the current process.
