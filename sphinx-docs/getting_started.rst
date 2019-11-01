============
Installation
============

------------
Requirements
------------

Installation requires Python 3.5+ (Developed and tested using Python 3.5).
Additional requirements that will be downloaded and installed automatically, include:

- click (>=7.0)
- Flask (>=1.0)
- frozendict (>=1.2)
- gunicorn (>=19.9)
- jsonschema (>=2.5.1)
- MarkupSafe (>=1.0)
- pymongo (>=3.7)
- PyYAML (>=3.11)
- pyzmq (>=17.0)
- Werkzeug (>=0.15)

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

In order to download and install Slivka choose the suitable zip or tar archive
form the repository_ and run install inside your virtual environment with
``pip install Slivka-<version>.(zip|tar)``.
Alternatively, you can install the most recent version directly from our github
repository with ``pip install git+git://github.com/warownia1/Slivka``.
Setuptools and all other requirements will be downloaded if not present, so internet
connection is required during the installation.

.. _repository: https://github.com/warownia1/Slivka/releases

After the installation, a new executable ``slivka-setup`` will be added to your Python
scripts directory. It can be used to initialize new Slivka projects. Make sure that it is
available in your ``PATH``.

--------------------
Creating new project
--------------------

In order to create a new Slivka project navigate to the folder where you want
it to be set-up and run the executable created during the installation. ::

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

The Slivka projects exist separately from the Slivka package and contain their own set
of configurations. You can create as many project as you like with one Slivka installations.
Each project contains three core files:

:manage.py:
  The main executable script which configures Slivka and runs its components.
:settings.yml:
  A settings file which defines project-wide parameters.
:services.yml:
  A list of available services with paths to their respective configuration files.
:wsgi.py:
  Module containing a wsgi application for dedicated wsgi servers.

The configuration files are unicode text files and can be edited with any text editor.
It is not advisable, however, to edit the main executable ``manage.py`` and ``wsgi.py``.

All additional service configurations files should be included in the services.yml file.
The details of adding service configurations will be explained in the following sections.

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
  On startup, ``SLIVKA_HOME`` environment variable is set to the absolute path of ``BASE_DIR``

  Examples:

  .. code-block:: yaml

    BASE_DIR: /home/slivka/project

    BASE_DIR: C:\Users\slivka\project

:``UPLOADS_DIR``:
  Directory where all user uploaded files are stored.
  It's recommended to serve files directly from this directory.
  It can be either an absolute path or a path relative to the ``BASE_DIR``.

  Default: ``./media/uploads``

:``JOBS_DIR``:
  A folder where job working directories are created and output files are stored.
  It's recommended to serve files directly from this directory.
  Can be either an absolute path or path relative to the ``BASE_DIR``.

  Default: ``./media/jobs``

:``LOG_DIR``:
  Path to directory where log files are to be stored.
  Can be either an absolute path or a path relative to the ``BASE_DIR``.

  Default: ``./logs``

:``SERVICES``:
  Path to the *services.yml* file containing the list of available services.
  Can be either an absolute path or a path relative to the ``BASE_DIR``.

  Default: ``./services.yml``

:``UPLOADS_URL_PATH``:
  The URL path where the uploaded files will be available from.
  This setting enables you to set the path so the files can be served by a proxy server
  e.g. Apache or Nginx. Serving media files through the python application is not recommended
  due to the limited number of simultaneous connections.

  Default: ``/media/uploads``

:``JOBS_URL_PATH``:
  The URL path where the tasks output files will be available from.
  This setting enables you to set the path so the files can be served by a proxy server
  e.g. Apache or Nginx. Serving media files through the python application is not recommended
  due to the limited number of simultaneous connections.

:``ACCEPTED_MEDIA_TYPES``:
  The list of media types that will be accepted by the server.
  Files having media types not specified in this list could not be uploaded to the server.

  Example:

  .. code-block:: yaml

    ACCEPTED_MEDIA_TYPES:
      - text/plain
      - application/json

:``SECRET_KEY``:
  Randomly generated key used for authentication. Not used currently and might be removed in the future.

:``SERVER_HOST``:
  The hostname which the server will be available at. Setting it to 0.0.0.0
  makes the application accept any incoming connection.
  If the slivka server is running behind a proxy, it's recommended to accept
  the connections from the proxy server only e.g. 127.0.0.1.

  *This parameter is only applicable when running slivka server through manage.py utility.
  When using other wsgi application such as uwsgi or Gunicorn refer to their documentation on
  how to specify the server host*

  *This parameter (along with SERVER_PORT) will be removed in the future*

:``SERVER_PORT``:
  Port used for listening to the HTTP requests. Remember that using  port number lower than 1024
  may be not allowed for regular users on your system.

  *This parameter is only applicable when running slivka server through manage.py utility.
  When using other wsgi application such as uwsgi or Gunicorn refer to their documentation on
  how to specify the server port*

  *This parameter (along with SERVER_PORT) will be removed in the future*

:``SLIVKA_QUEUE_ADDR``:
  Binding socket of the slivka queue. Can be either tcp or ipc socket.
  **It's highly recommended to use localhost, since accepting connections**
  **from the outside may be a security issue.**

  Example:

  .. code-block:: yaml

    SLIVKA_QUEUE_ADDR: 127.0.0.1:3397

  .. code-block:: yaml

    SLIVKA_QUEUE_ADDR: /home/slivka/local-queue.sock

:``MONGODB_ADDR``:
  The connection address to the mongo database.
  It should be a full `mongodb URI`_ e.g. ``mongodb://mongodb0.example.com:27017``
  or a simple hostname e.g. ``127.0.0.1:27017``.
  This parameter is passed directly to the ``pymongo.MongoClient``

.. _mongodb URI: https://docs.mongodb.com/manual/reference/connection-string/

----------------------
Services configuration
----------------------

The services configuration file (*services.yml* by default) lists all available services
and paths to their respective configuration files along with their metadata.
A separate service can be a different executable or a different set of options
for the same executable.
Each service name is a key of the JSON object and each value should have
``label``, ``form``, ``command``, ``presets`` and ``classifiers`` parameters.

.. code-block:: yaml

  example:
    label: Example service
    form: conf/example_form.yml
    command: conf/example_command.yml
    classifiers:
    - "Topic :: Example"
    - "Operation :: Testing :: Operation testing"

:``label``:
  A human readable name of the service.

:``form``:
  The path to the form definition file described in the `Form Description`_ section.

:``command``:
  The path to the command configuration file whose structure is described in the
  `Command Configuration`_ section.

:``presets``:
  Optional parameter pointing to the file containing input parameter presets
  described in the section `Presets`_.

:``classifiers``:
  A list of categories or tags that this service falls into. There is no strict rule
  of how the classifiers are defined and you are free to tag the services as you wish.

----------------
Form Description
----------------

Form description file specifies the parameters which are exposed to the front end user
through the web API.
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
value         `Value Object`_                 **Required.** Value object which provides
                                              information about the expected value.
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
However ``type``, ``required`` and ``default`` properties are common for every field type.

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

``type: int``

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

``type: float`` or ``decimal``

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

  type: decimal
  min: -4.0
  minExclusive: false
  max: 4.5
  maxExlusive: true
  default: 0

Text Value object
-----------------

``type: text``

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

``type boolean`` or ``flag``

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

``type: choice``

============ ======================== ==========================
 Field Name   Type                     Description
============ ======================== ==========================
 choices      object[string, string]   List of available choices.
                                       Keys should represent the values presented to the user
                                       while values the command line parameter the choice is interpreted as.
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

``type: file``

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


---------------------
Command configuration
---------------------

Command configuration tells Slivka how to construct the command line parameters
for the executable file and how to submit it to the queuing system along with
extra arguments and environment variables.
The file follows YAML format (JSON is also allowed) and needs to have the following
properties:

=============== ================================ ================================================
 Field name      Type                                 Description
=============== ================================ ================================================
baseCommand     array[string]                    A list of command arguments appearing
                                                 before any other parameters.
env             map[string, string]              Additional environment variables which will be
                                                 set for the job.
inputs          map[string, `Argument Object`_]  A mapping of field values to the command
                                                 line parameters. Each property name corresponds
                                                 to the field name in the form definition file.
arguments       array[string]                    A list of arguments appended after any other parameters
outputs         map[string, `Output Object`_]    Collection of output files produced by
                                                 the command line program.
runners         map[string, `Runner Object`_]
limiter         string
=============== ================================ ================================================

Argument Object
===============
Each key (property name) specified in the inputs is mapped to the field with the same name
defined in the form description file.
If you want to add a command line parameter which doesn't have a corresponding form field
it is recommended to prepend the name with an underscore ``_``.
Note that this parameter value will always be empty and will be skipped
unless a default value is provided.

Each argument object corresponds to a single command line parameter passed
to the executable. They will be inserted in the order they are listed in the
configuration file skipping those having empty values.
Each argument object have one required property ``arg`` which is a template for
the command line argument. The value will be substituted for ``$(value)`` placeholder.
You are also allowed to use environment variables using standard bash syntax ``${VARIABLE}``.
There is a special environment variable ``SLIVKA_HOME`` available which contains the path
to the slivka project base directory.
Optionally you may add ``value`` proeprty if you want to specify a default value
or ``type`` if the type is other than string.

============ ====== =============================
 Field Name   Type   Description
============ ====== =============================
arg          string **Required.** Command line parameter template.
type         string Type of the value, allowed values are string, number, flag, file or array.
                    Defaults to string if not specified.
value        any    Value used if no other value is provided.
symlink      string Destination where the input file will be linked to. Parameter value is then
                    changed to the symlink path. Available only with ``type: file``
join         string Character used to join multiple values provided for the command parameter.
                    The parameter will be repeated for each value if ``join`` is not specified.
                    Available only with ``type: array``
============ ====== =============================


Here is an exmaple of the command line parameters definition corresponding
to the form having ``file``, ``inputformat``, ``outputformat`` fields:

.. code-block:: yaml

  baseCommand:
  - json-converter

  inputs:
    inputformat:
      arg: --in-format=$(value)
      type: string
    outputformat:
      arg: --out-format=$(value)
      type: array
      join: ","
    file:
      arg: $(value)
      type: file
      symlink: input.txt


If the following values provided

- ``file: /home/slivka/media/input.json``
- ``inputformat: xml``
- ``outputformat: [yaml, json]``

The constructed command line is going to be ::

  json-converter --in-format=xml --out-format=yaml,json input.txt

and */home/slivka/media/input.json* will be linked to */job/working/directory/input.txt*.

Output Object
=============

Output objects describe files or a groups of files created by the command.
Each output object have the following properties:

============ ====== =======================================================
 Field Name   Type   Description
============ ====== =======================================================
path         string **Required.** Path to the output file relative to the
                    job's working directory. Glob patterns are supported.
media-type   string Media (mime) type of the file.
============ ====== =======================================================

The standard output and standard error are redirected to *stdout* and
*stderr* respectively so these names may be used to indicate
standard output and error streams respectively.
The paths are evaluated lazily when the output files are requested and match
as many files as possible. Every defined result file is treated as optional
and its absence on job completion does not raise any error.

Example:

.. code-block:: yaml

  outputs:
    output:
      path: outputfile.xml
      media-type: application/xml
    auxillary:
      path: *_aux.json
      media-type: application/json
    log:
      path: stdout
      media-type: text/plain
    error-log
      path: stderr
      media-type: text/plain


Runner Object
=============

So far, the configuration regarded the construction of command line arguments.
The runner object defines the way those commands are actually executed on the system.
By default, the ``default`` runner is always selected. This behaviour can be overridden
by providing a limiter script described in the advanced usage section.

Each runner object have two properties ``class`` and ``parameters``.

============ =================== =========================================================
 Field Name   Type                Description
============ =================== =========================================================
class        string              **Required.** Python path to the class extending
                                 ``Runner`` interface. Built-in runners: SlivkaQueueRunner,
                                 GridEngineRunner and ShellRunner do not require full path
                                 but class name only.
parameters   map[string, any]    Additional keyword arguments passed to the Runner constructor.
                                 Refer to the specific runner instance for details.
============ =================== =========================================================

Example:

.. code-block:: yaml

  runners:
    local:
      class: SlivkaQueueRunner
    default:
      class: GridEngineRunner
      parameters:
        qsub_args:
        - -P
        - webservices
        - -q
        - 64bit-pri.q
        - -l
        - ram=3400M

-------
Presets
-------

It is possible to pre-define commonly used sets of parameters to give the users an idea
of useful input parameter combinations. The configuration file should have a single
``presets`` property containing the list of preset object defined below.

============ ================ =================================================================
 Field name   Type             Description
============ ================ =================================================================
id           string           **Required.** Unique identifier of this preset.
name         string           **Required.** Short name of the preset.
description  string           Additional details of the configuration.
values       map[string, any] **Required.** Mapping of form fields to the pre-configured values.
============ ================ =================================================================

The presets serve as a hint for the users only and the use of the pre-defined values
is not enforced.

=====================
Launching the Project
=====================

Slivka consists of two core parts: RESTful HTTP server and job scheduler (dispatcher)
and an additional worker queue included to run tasks
on the local machine without additional queuing system installed.
Their separation allows to run those parts independently of each other.
In situaitions when the scheduler is down, the server keeps collecting
the requests stashing them in the database, so when the scheduler is working
again it can catch up with the server and dispatch all pending requests.
Similarly, when the server is down, the currently submitted jobs 
are unaffected and can still be processed.

Each component can be started using the *manage.py* script created in the project's
root directory.

Before you start, make sure that you set up and run a mongodb server on your machine
so that slivka can use it to store and exchange data between processes.

Next, you need to launch the REST server and the scheduler processes. ::

  python manage.py server -t gunicorn

::

  python manage.py scheduler

It will automatically set up gunicorn server to listen on the address specified in the
*settings.yml* file and lanch the main scheduler.

If you want to have more control or decided to use different wsgi application
to run the server, you can use *wsgi.py* script provided in the project directory.
Here is an example of starting slivka server with gunicorn ::

  gunicorn -b 0.0.0.0:8000 -w 4 -n slivka-http wsgi

If you decide to use the local queue to execute jobs, you can start it with ::

  python manage.py local-queue

To stop any of these processes, send the ``SIGINT`` (2) "interrupt" or
``SIGTERM`` (15) "terminate" signal to the process or press **Ctrl + C**
to send ``KeyboardInterrupt`` to the current process.
