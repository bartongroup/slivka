============
Installation
============

------------
Requirements
------------

Installation requires Python 3.5+ (version 3.7 recommended).
Additional requirements that will be downloaded and installed automatically, include:

- attrs (>=19)
- click (>=7.0)
- Flask (>=1.0)
- frozendict (>=1.2)
- gunicorn (>=19.9) (optional)
- jsonschema (>=2.5.1)
- MarkupSafe (>=1.0)
- pymongo (>=3.7)
- PyYAML (>=3.11)
- pyzmq (>=17.0)
- simplejson (>=3.16)
- uwsgi (>=2.0) (optional)
- Werkzeug (>=0.15)

-------------------------
Installing Slivka package
-------------------------

It's recommended to install Slivka inside a virtual environment using virtualenv or conda.

You can install virtualenv by running ``pip install virtualenv`` (on some Linux distributions
you may need to install a correspinding system package e.g. ``apt-get install python-virtualenv``).
Run ``virtualenv env``, wait for it to create a new environment in ``env``
directory and activate using ``source env/bin/activate`` on Unix/OS X or
``env\Scripts\activate.bat`` on Windows.
More information about the virtualenv package can be found in `virtualenv documentation`_.

For conda users, create a new environment using ``conda create -n slivka python=3.7``
and activate with ``conda activate slivka``.
More details can be found in `conda documentation`_.

.. _`virtualenv documentation`: https://virtualenv.pypa.io/en/stable/
.. _`conda documentation`: https://conda.io/en/latest/

Slivka package can be installed directly from the github repository with pip.
We recommend using development branch until the first stable version is released.
``pip install git+git://github.com/warownia1/Slivka@dev``.
Setuptools and all other requirements will be downloaded if not present, so internet
connection is required during the installation.

After the installation, a new executable ``slivka-setup`` will be added to your Python
scripts directory. It will be used to create a new empty slivka configuration.
You can also use existing configurations created by other people.

--------------------
Creating new project
--------------------

In order to create a new Slivka project navigate to the folder where you want
it to be set-up and run the ``slivka-setup`` executable created during
the installation ::

   slivka-setup <name>

replacing ``<name>`` with the name of the directory where configuration files
will be copied to.
Use ``.`` if you wish to set-up the project in the current directory.
If the executable cannot be accessed (e.g. it is not in the PATH), you
can equivalently run the slivka module with ::

   python -m slivka <name>

The installation will create a new directory ``<name>`` if one does not exist
and copy example configuration files and service into it.
In the following sections we walk through the process of creating and configuring
new services.

=================
Project Structure
=================

First, let us take a look at the overall structure of the newly created project.
There are four files in the project root directory as well as *conf* and *scripts*
directories.

:manage.py:
  Main executable script which loads all configuration files and starts
  necessary processes.
:settings.yml:
  General configuration file containing project-wide parameters.
  Refer to `settings file`_ section for more information about available
  parameters.
:services.yml:
  List of available services and paths to their respective configuration files.
  Refer to `services list`_ for more details.
:wsgi.py:
  Module containing a wsgi application as specified in `PEP-3333`_
  used by the dedicated wsgi middleware.
:conf:
  Directory containing configuration files for all available services.
  Refer to `form definition`_ and `command configuration`_ section for more
  information on creating web forms for command line tools.

.. _`PEP-3333`: https://www.python.org/dev/peps/pep-3333/

All the configuration files are using `YAML <https://yaml.org/>`_ format
which can be edited with any text editor.
If you are not familiar with YAML syntax you can use JSON instead since
any JSON document is a valid YAML document.

It's not advisable to edit *manage.py* and *wsgi.py* scripts unless
you are an advanced user and you know what you are doing.

-------------
Settings file
-------------

``settings.yml`` is a yaml file containing parameters used throughout the
application. All parameters are case sensitive and their names should be
written in capital letters.

The following parameters are recognised by the application:

:``BASE_DIR``:
  Location of the project directory.
  Absolute paths are preferred to relative paths which are resolved with
  respect to the current working directory the process was started at.
  All other relative paths which appear in the configuration files start at
  the ``BASE_DIR`` path.
  It defaults to the project root directory containing the ``manage.py`` file.
  Additionally, slivka sets ``SLIVKA_HOME`` environment variable storing the
  absolute ``BASE_DIR`` path which can be used whenever
  the path to the project directory is needed.

  Examples:

  .. code-block:: yaml

    BASE_DIR: /home/my-username/my-slivka
    BASE_DIR: C:\Users\my-username\my-slivka

:``UPLOADS_DIR``:
  Directory for user uploaded files.
  It can be either an absolute path or a path relative to the ``BASE_DIR``.

  Default: ``./media/uploads``

  .. note::
    If slivka is served behind a reverse proxy, it's recommended to configure
    the proxy server to send files directly from this directory to reduce
    the load put on the python application.

:``JOBS_DIR``:
  Directory where job working directories are created and output files are stored.
  Can be either an absolute path or path relative to the ``BASE_DIR``.

  Default: ``./media/jobs``

  .. note::
    If slivka is served behind a reverse proxy, it's recommended to configure
    the proxy server to send files directly from this directory to reduce
    the load put on the python application.

:``LOG_DIR``:
  Log files directory location.
  Can be either an absolute path or a path relative to the ``BASE_DIR``.

  Default: ``./logs``

:``SERVICES``:
  Path to the *services.yml* file containing the list of available services.
  Can be either an absolute path or a path relative to the ``BASE_DIR``.
  More information about the services list in the `services list`_ section.

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

  .. note::
    This parameter is only applicable when running slivka server through manage.py utility.
    When using other wsgi application directly, refer to their documentation on
    how to specify the server host


:``SERVER_PORT``:
  Port used for listening to the HTTP requests. Remember that using  port number lower than 1024
  may be not allowed for regular users on your system.

  .. note::
    This parameter is only applicable when running slivka server through manage.py utility.
    When using other wsgi application directly, refer to their documentation on
    how to specify the server port


:``SLIVKA_QUEUE_ADDR``:
  Binding socket of the slivka queue. Can be either tcp or ipc socket.
  **It's highly recommended to use localhost or named pipes.**
  **Accepting external connections is a security issue.**

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

-------------
Services list
-------------

The services configuration file (*services.yml* by default) lists all available services
and paths to their respective configuration files along with their metadata.
The common use case is to create an individual service for each tool
you want to make available on your server.

Each top level key represents service name that serves as an identifier,
it must be unique and contain alphanumeric characters only.
Using lowercase letters only is recommended.

Each section should contain the following parameters:

:``label``:
  **required** A human readable name of the service.

:``form``:
  **required** The path to the form definition file described in the
  `Form Definition`_ section.

:``command``:
  **required** The path to the command configuration file whose structure is
   described in the `Command Configuration`_ section.

:``presets``:
  Path to the file containing parameter presets described in the `Presets`_ section.

:``classifiers``:
  A list of categories or tags that this service fits into. There is no strict rule
  of how the classifiers are defined and you are free to tag the services as you wish.

Example:

.. code-block:: yaml

  example:
    label: Example service
    form: conf/example_form.yml
    command: conf/example_command.yml
    classifiers:
    - "Topic :: Example"
    - "Operation :: Testing :: Operation testing"

---------------
Form Definition
---------------

Form description file specifies the parameters which are exposed to the front end user
through the web API.
It contains the list of modifiable properties which will be submitted to the new job.
Each top level key defines a unique field name, only alphanumeric characters,
hyphen and underscore are allowed and using lowercase letters only is recommended.
The values for each key define additional information about the field and 
constrains of accepted values.
The following section defines allowed parameters for each field.

Field Object
============

============= ================== =================
 Key           Type               Description
============= ================== =================
label         string             **Required.** A human readable field name.
description   string             Detailed information about the field 
                                 a.k.a. help text
value         `Value Object`_    **Required.** Details about accepted value
                                 type and constraints.
============= ================== =================

Example of the form accepting two fields: *input* and *format* is shown below.

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

Value objects contain the information about the field type and value contraints.
The parameter specified here are used to validate the user-provided parameters.
The configurable properties differ depending on the field type.
Properties: ``type``, ``required`` and ``default`` are available regardless
of the field type.

============ ========== ========================
 Key          Type       Description
============ ========== ========================
 type         string     **Required.** Type of the field,
                         must be: int, float, text, boolean, choice or file.
 required     boolean    **Required.** Whether the value for that field must be provided.
                         Default is *True* if not specified.
 default      any        Default value used when the user does not specify that parameter.
                         Its type must match the type of the field.
============ ========== ========================


Note that supplying the default value automatically makes the field not required 
since the default value is used when the field is left empty.

All other properties listed below are optional and are specific to
their respective field types.

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

============ ======================== ==========================================
 Field Name   Type                     Description
============ ======================== ==========================================
 choices      map[string, string]      Mapping of available choices where keys represent
                                       the values presented to the user
                                       and values the command line parameters
                                       substituted for that choice.
============ ======================== ==========================================

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
for the program and how to submit it to the queuing system along with
extra arguments and environment variables.

=============== ================================ ================================================
 Field name      Type                             Description
=============== ================================ ================================================
baseCommand     array[string]                    **Required.** A list of command arguments appearing before any other parameters.
env             map[string, string]              Additional environment variables which will be
                                                 set for this job.
inputs          map[string, `Argument Object`_]  **Required.** A mapping of field values to the command
                                                 line parameters. Each key corresponds
                                                 to the field name in the form definition file
                                                 and the value is an argument object described below.
arguments       array[string]                    A list of arguments added at the end of the command.
outputs         map[string, `Output Object`_]    **Required.** Collection of output files produced by
                                                 the command line program.
runners         map[string, `Runner Object`_]    **Required.** Collection of runner configurations
                                                 that will be used to send jobs to the queuing systems.
limiter         string                           Path to the python class which will assign jobs to
                                                 appropriate runners (see `Advanced Usage <advanced_usage.html#limiters>`_)
=============== ================================ ================================================

Argument Object
===============
Each key (property name) specified in the inputs is mapped to the field with the same name
defined in the form description file.
If you want to add a command line parameter which doesn't have a corresponding form field
it is recommended to prepend the name with an underscore ``_`` to distinguish it
from arguments taken from the input form.
Note that the value of this parameter will always be empty and will be skipped
unless a default value is provided.

Each argument object corresponds to a single command line parameter passed
to the executable. They will be inserted in the order they are listed in the
configuration file skipping those having empty values.
Each argument object have one required property ``arg`` which is a command
line argument template. Use ``$(value)`` placeholder to refer to the value supplied by the user.
You can also use environment variables using unix syntax ``${VARIABLE}``.
Additionally, there is a special environment variable ``SLIVKA_HOME`` available
which contains the path to the slivka project base directory.

If the type of the parameter is other than string, you must specify ``type`` parameter
to ensure proper value conversion.
Optionally you may add ``value`` property if you need to specify a default value.
This value will be used if the field was not provided by the form. It's expecially
useful when defining constant command line arguments.

============ ====== =============================
 Field Name   Type   Description
============ ====== =============================
arg          string **Required.** Command line parameter template.
type         string Type of the value. Allowed values are string, number, flag, file or array.
                    Defaults to string if not specified.
value        any    Value used if no matching value is provided by the form.
symlink      string Some command line programs require input file to sit in the current working directory.
                    Use this parameter to set the name of the link that will be created in the
                    job's current working directory. Available only with ``type: file``
join         string Character used to join values if multiple values are provided.
                    If join is not defined, the argument will be repeated for each value.
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

and */job/working/directory/input.txt* will be a sumlink pointing to
*/home/slivka/media/input.json*.

Output Object
=============

Output objects describe individual files or groups of files created by the
command line program. Each output object have the following properties:

============ ====== =======================================================
 Field Name   Type   Description
============ ====== =======================================================
path         string **Required.** Path to the output file relative to the
                    job's working directory. Glob patterns are supported.
media-type   string Media (mime) type of the file.
============ ====== =======================================================

The standard output and standard error are redirected to *stdout* and
*stderr* respectively so these names may be used to fetch the content of
the standard output and error streams respectively.
The paths are evaluated lazily whenever the output files are requested and match
as many files as possible. Every defined result file is treated as optional
and its absence on job completion does not raise any error.

Example:

.. code-block:: yaml

  outputs:
    output:
      path: outputfile.xml
      media-type: application/xml
    auxiliary:
      path: "*_aux.json"
      media-type: application/json
    log:
      path: stdout
      media-type: text/plain
    error-log:
      path: stderr
      media-type: text/plain


.. warning::
  Patterns starting with special characters must be quoted.


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
    default:
      class: SlivkaQueueRunner
    grid_engine:
      class: GridEngineRunner
      parameters:
        qsub_args:
        - -P
        - webservices
        - -q
        - 64bit-pri.q
        - -l
        - ram=3400M


For non-advanced users it's recommended to set the default runner to
``SlivkaQueueRunner`` which uses no additional parameters.

-------
Presets
-------

It is possible to pre-define commonly used sets of parameters to provide users
with useful input parameter combinations. The configuration file should have a single
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

If you want to use the default local queue to execute jobs, you can start it with ::

  python manage.py local-queue

To stop any of these processes, send the ``SIGINT`` (2) "interrupt" or
``SIGTERM`` (15) "terminate" signal to the process or press **Ctrl + C**
to send ``KeyboardInterrupt`` to the current process.
