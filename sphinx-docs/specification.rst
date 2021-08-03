*************
Specification
*************

=================
Project Structure
=================

The collection of configuration files used be slivka is referred to
as a slivka project. The root directory housing other configuration
files is referred to as a slivka home directory. On startup, slivka
also creates an environment variable ``SLIVKA_HOME`` pointing to that
directory, which can be used throughout the configuration files and
scripts.

Each project contains few files essential for the proper operation
of slivka. Those are:

:config.yaml:
  Main configuration file of the slivka project, required for its 
  proper functionality.
  Typically, slivka recognises the project directory as
  the one containing this file. Alternatively, it can be named
  *settings.yaml* and either *.yaml* or *.yml* extension is allowed.
  The detailed information about the file syntax and parameters is
  provided in the `configuration file`_ section.
:wsgi.py:
  A python module file containing a wsgi-compatible application as specified in 
  `PEP-3333`_. This file is used by wsgi middleware to serve slivka
  http endpoints. You may want to use this file if you plan to use
  an unsupported middleware or have more control over execution parameters.
:manage.py:
  A legacy executable script that may be used to load configuration 
  files and start slivka processes. It's functionality is fully replaced
  by the newer *slivka* executable.
:services:
  A default directory containing service configuration files. Each file
  in the directory whose name ends with *.service.yaml* is considered
  a slivka service file. The directory can be changed in the main
  configuration file. 

.. _`PEP-3333`: https://www.python.org/dev/peps/pep-3333/

All the configuration files are using `YAML <https://yaml.org/>`_ syntax 
and can be edited with any text editor.
If you are not familiar with YAML structure you can use JSON instead since
any JSON document is a valid YAML document as well.

It's not advisable to edit *manage.py* and *wsgi.py* scripts unless
you are an advanced user and you know what you are doing.

==================
Configuration file
==================

*config.yaml* is the main configuration file of the project and
stores values used across the application.
The properties in the file can be structured as a tree or a flat mapping
as shown in the following snippets respectively. Both forms are equivalent.

.. code:: yaml

  directory.uploads: media/uploads
  directory.jobs: media/jobs

.. code:: yaml

  directory:
    uploads: media/uploads
    jobs: media/jobs

Here is the list of parameters that can be defined in the file.
All of them are required unless stated otherwise.

:*version*:
  Version of the configuration file syntax used to check for project
  compatibility. For the current slivka version this must be set to ``"0.3"``.

..

:*directory.uploads*:
  Path to a directory where the files uploaded by the users will be stored.
  A relative path is resolved with respect to the project
  directory. It's recommended to set the proxy server to serve
  those files directly, i.e. under */uploads* path (configurable
  by changing ``server.uploads-path``).
  Default is ``"./media/uploads"``.

:*directory.jobs*:
  Path to a directory where the job sub-directories will be created.
  For each job, slivka creates a sub-directory there and sets it as a
  current working directory.
  A relative path is resolved with respect to the project directory.
  It's recommended to set the proxy server to serve those files
  directly, i.e. under */jobs* path (configurable by changing
  ``server.jobs-path``).
  Default is ``"./media/jobs"``

:*directory.logs*:
  Path to the directory where the log files will be stored.
  Default is ``"./logs"``

:*directory.services*:
  Path to the directory containing service definition files.
  Slivka automatically detects files under this directory whose
  names end with ``.service.yaml`` as services and loads them on startup.
  Default is ``"./services"``

..

:*server.host*:
  Address and port under which slivka application is hosted.
  It's highly recommended to run slivka behind a HTTP proxy server
  such as `nginx`_, `Apache HTTP Server`_ or `lighttpd`_ ,
  so no external traffic connects to the wsgi server directly.
  Set the value to the address where the proxy server connect from or
  ``0.0.0.0`` to accept connections from anywhere (not recommended).
  Default is ``127.0.0.1:4040``.

:*server.uploads-path*:
  Path where the uploaded files are served at. It should be set to
  the same path that the proxy server uses to serve files from the
  uploads directory (set in *directory.uploads* parameter).
  Default is ``"/media/uploads"``.

:*server.jobs-path*:
  Path where the job results are server at. It should be set to the
  same path that the proxy server uses to server files from the
  jobs directory (set in *directory.jobs* parameter).
  Default is ``"/media/jobs"``.

:*server.prefix*:
  *(optional)* Url path that the proxy server serves the application
  under if other then root. This is needed for the urls and redirects
  to work properly. For example, if you configured your proxy
  server to redirect all requests starting with */slivka* to the
  wsgi application, then set the prefix value to ``/slivka``.

  .. note::

    Configure your proxy rewrite rule to **not** remove the prefix
    from the url.

.. _nginx: https://nginx.org/
.. _Apache HTTP Server: https://httpd.apache.org/
.. _lighttpd: https://www.lighttpd.net/

:*local-queue.host*:
  Host and port where the local queue server will listen to commands on.
  Use localhost address or a named socket that only trusted users
  (i.e. slivka) can write to.
  You may specify the protocol ``tcp://`` for tcp connections.
  The ``ipc://`` or ``unix://`` protocol must be specified when using
  named sockets.
  Default is ``tcp://127.0.0.1:4041``.

  .. warning::

    NEVER ALLOW UNTRUSTED CONNECTIONS TO THAT ADDRESS since arbitrary
    code may be sent to and executed by the queue.

..

:*mongodb.host*:
  *(optional)* Address and port of the mongo database that slivka will connect to.
  Either one of this or *mongodb.socket* parameter must be present.
  Default is ``127.0.0.1:27017``.

:*mongodb.socket*:
  *(optional)* Named socket where mongo database accepts connections at.
  Either one of this or *mongodb.host* parameter must be present.

:*mongodb.username*:
  *(optional)* Username that the application will use to log in to the
  database. A default user will be used if not provided.
  Default is unset.

:*mongodb.password*:
  *(optional)* Password used to authenticate the user when connecting
  to the database. Default is unset.

:*mongodb.database*:
  Database that will be used by slivka application to store data.
  Default is ``slivka``

========
Services
========

Slivka creates the services using the service definition files located in the
directory specified in the *settings.yaml* file (*services/* by default).
Each service definition is stored in its unique file named *<name>.service.yaml*
where the service name should be substituted for *<name>*.
The filename (without the extension) should contain alphanumeric characters, 
dashes and underscores only and will be used as a unique service identifier.
Using lowercase letters is recommended but not required.
There is no limit on the number of services that can be created.

----------------
Service Metadata
----------------

The first thing that should be included in the service definition file is
its metadata.

First, specify a ``label`` that will be shown to the users.
Therefore, it should be short and descriptive.

Next, there are service ``classifiers`` - a list of tags that allow to categorise
the service based on inputs/outputs or performed operation.
There are no rules imposed on classifiers but ideally they should be both human and
machine readable.

Example:

.. code-block:: yaml

  label: MyService
  classifiers:
    - Purpose=Example
    - Type=Tutorial

----
Form
----

Forms in slivka serve similar purpose to the web forms -- they are collections of
fields representing input parameters that can be provided by the users.
The form defines which service parameters are exposed through
the web API and hence modifiable by the users. Those values are later
passed to the program in the command line building process.

The form is defined under the ``form`` key. It consists of the mapping
of field names to `field object`_.
Each unique name should contain alphanumeric characters (preferably lowercase),
dashes and underscores only. They will be used by slivka to identify fields
and used in HTTP requests.

Field object
============

Each element of the form definition consists of the key-value pair
where key is the field name and the value is the *field object*
having the following properties:

.. list-table::
  :widths: auto
  :header-rows: 1

  * - Key
    - Type
    - Description
  * - label
    - string
    - **Required.** A human readable field name.
  * - description
    - string
    - Detailed information about the field / Help text
  * - value
    - `Value Object`_
    - **Required.** Accepted value metadata: type and constraints


Example of the form accepting two fields: *input* and *filename* is shown below:

.. code-block:: yaml

  input:
    label: Input file
    description: JSON, YAML or XML file containing input data.
    value:
      type: file
  filename:
    label: Filename
    value:
      type: text

.. _parameter-specification:

Value object
============

The value object contains the metadata defining the accepted value type and
constraints. Those parameters are used to validate the user-provided input.
The available constraints differ depending on the field type; however,
properties: ``type``, ``required``, ``default`` and ``multiple`` are
available for all field types.

.. list-table::
  :widths: auto
  :header-rows: 1

  * - Key
    - Type
    - Description
  * - type
    - string
    - **Required.** Type of the field, must be either one of the built-in
      types: int, decimal, text, flag, choice or file; or the path to the
      custom field class.
  * - required
    - boolean
    - Whether the field value must be provided by the user. Default: yes
  * - default
    - any
    - Default value used if no value is provided by the user. The default
      value must also meet all value constraints.
  * - multiple
    - boolean
    - Whether the field accepts multiple values. Default: no

Note that specifying the default value automatically makes the field not
required since the default value is used when the field is left empty.

All other parameter listed below are optional and are specific to
their respective field types.

int type
--------

===== ========= =========================
 Key   Type      Description
===== ========= =========================
min   integer   Minimum value, unbound if not provided.
max   integer   Maximum value, unbound if not provided.
===== ========= =========================

Example:

.. code-block:: yaml

  type: int
  required: true
  min: 0
  max: 10
  default: 5


decimal type
------------

============== ======= =======================================
 Key            Type    Description
============== ======= =======================================
min            float   Minimum value, unbound if not provided.
max            float   Maximum value, unbound if not provided.
min-exclusive  boolean Whether the minimum should be excluded.
max-exclusive  boolean Whether the maximum should be excluded.
============== ======= =======================================

Example:

.. code-block:: yaml

  type: decimal
  min: -4.0
  min-exclusive: false
  max: 4.5
  max-exclusive: true
  default: 0

text type
---------

=========== ======== ===============================
 Key         Type     Description
=========== ======== ===============================
min-length  integer  The minimum length of the text.
max-length  integer  The maximum length of the text.
=========== ======== ===============================

Example:

.. code-block:: yaml

  type: text
  min-length: 1
  max-length: 8

flag type
---------

===== ========= =========================
 Key  Type      Description
===== ========= =========================
 *(no additional properties)*
=========================================

Example:

.. code-block:: yaml

  type: flag
  default: false

choice type
-----------

.. list-table::
  :widths: auto
  :header-rows: 1

  * - Key
    - Type
    - Description
  * - choices
    - map[str, str]
    - Mapping of available choices where the user choses one of the keys
      which is then converted to the value on the server side

Example:

.. code-block:: yaml

  type: choice
  choices:
    Alpha: --alpha
    Beta: --no-alpha
    Gamma: --third-option
  default: Alpha

file type
---------

.. list-table::
  :header-rows: 1
  :widths: auto

  * - Key
    - Type
    - Description
  * - media-type
    - string
    - Accepted media type (e.g. text/plain, application/json).
  * - media-type-parameters
    - map[str, any]
    - Auxiliary media type information/constraints.
  * - max-size
    - string
    - The maximum file size in bytes. Decimal unit prefixes are allowed
      (e.g. 1024B, 500KB or 10MB).

Example:

.. code-block:: yaml

  type: file
  media-type: text/plain
  media-type-parameters:
    max-lines: 100
  max-size: 1KB


------------------
Command definition
------------------

Command configuration tells Slivka how to construct the command line parameters
for the program and what environment variables should be set.
The command definition appears under ``command`` key in the service file.

.. list-table::
  :widths: auto
  :header-rows: 1

  * - Key
    - Type
    - Description
  * - baseCommand
    - str or array[str]
    - **Required.** A list of command line arguments appearing before any
      other parameters.
  * - inputs
    - map[str, `Input Object`_]
    - **Required.** The instructions how the form inputs are mapped to
      the command line arguments.
  * - env
    - map[str, str]
    - Environment variables that will be set for the process.
  * - arguments
    - array[str]
    - Additional arguments added after the input parameters.
  * - outputs
    - map[str, `Output Object`_]
    - **Required.** Output files produced by the command line program.


Input Object
============
Each key (field name) specified in the inputs is linked to the 
corresponding field in the form definition.
The value provided by the user will be used to construct each command
line parameter.
If you want to add an argument which is not mapped to the
form field it is recommended to indicate it by prepending the name with
an underscore ``_`` to distinguish it from arguments taken from the input form.
Note that the value of this parameter will always be empty and will be skipped
unless a default value is provided.

Each input object corresponds to a single command line parameter passed
to the executable. They will be inserted in the order they appear in the
file skipping those having empty values.

.. list-table::
  :header-rows: 1
  :widths: auto

  * - Key
    - Type
    - Description
  * - arg
    - string
    - **Required.** Command line parameter template. Use ``$(value)``
      as the placeholder for the input value.
  * - type
    - string
    - Parameter type ensuring proper type conversion.
      One of: ``string``, ``number``, ``flag``, ``file`` or ``array``.
      Defaults to string if not specified.
  * - value
    - any
    - Default value used if no value was provided in the form.
  * - symlink
    - string
    - Name of the symlink created in the job's working directory
      pointing to the input file. Applicable with file type only.
  * - join
    - string
    - A delimiter used to join multiple values. The parameter will be
      repeated for multiple values if not specified.
      Applicable with array type only.

Each argument object have one required property ``arg`` which is a command
line argument template. Use ``$(value)`` placeholder to refer to the 
value supplied by the user in the form. You can also use environment variables 
using ``${VARIABLE}`` syntax. Additionally, a special environment variable
``SLIVKA_HOME`` pointing to the slivka project directory is available. 

If the type of the parameter is other than string, you must specify 
``type`` parameter to ensure proper value conversion. Optionally you 
may add ``value`` property if you need to specify a default value.
This value will be used if the field was not given in the form. 
It's especially useful when defining constant command line arguments.

Here is an example configuration of the command line program
*json-converter* taking two options ``--in-format`` and ``--out-format``
and input file argument, with the corresponding form 
having ``file``, ``inputformat`` and ``outputformat`` fields:

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


For the following input parameters:

- file = ``/home/slivka/media/input.json``
- inputformat =  ``xml``
- outputformat =  ``[yaml, json]``

The constructed command line is

.. code-block:: sh

  json-converter --in-format=xml --out-format=yaml,json input.txt

and */home/slivka/media/input.json* is automatically symlinked to
*/job/working/directory/input.txt*

.. warning::
  **Never** write a service which executes code received from an 
  untrusted source. One example is to run user provided text as
  a shell command:

  .. code-block:: yaml

    baseCommand: sh
    inputs:
      command:
        arg: -c $(value)
  

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
  Patterns starting with a special characters must be quoted.

.. _runners-spec:

-------
Runners
-------

So far, the configuration regarded the construction of command line arguments.
The ``runners`` define how these commands are executed on the system.
Each key in the runners section is the name of the runner and the value
is an object having following fields:

.. list-table::
  :widths: auto
  :header-rows: 1

  * - Key
    - Type
    - Description
  * - class
    - string
    - **Required.** A name of a built-in runner type or a path to the class
      extending the ``slivka.scheduler.Runner`` interface.
      Currently available runners are ``SlivkaQueueRunner`` and
      ``GridEngineRunner``
  * - parameters
    - map[str, any]
    - Additional parameters passed to the runner. Available parameters
      depend on the runner constructor.

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
``SlivkaQueueRunner`` which takes no additional parameters.
``GridEngineRunner`` takes one parameter -- ``qsub_args`` -- containing
the list of arguments passed directly to the qsub command.

Limiter
=======

Limiter allows controlling the selection of the runner based on the input
parameters. The value should be a path to the class extending
``slivka.scheduler.Limiter``. The usage of limiters is covered in
the `advanced usage`_

.. _`advanced usage`: advanced_usage.html#limiters

Presets
=======

It is possible to pre-define commonly used sets of parameters to provide users
with frequently used parameters combinations using ``presets`` property
containing the list of preset objects defined below.

.. list-table::
  :widths: auto
  :header-rows: 1

  * - Key
    - Type
    - Description
  * - id
    - string
    - **Required.** Unique preset identifier.
  * - name
    - string
    - **Required.** Short name of the preset.
  * - description
    - string
    - More detailed description of the parameters set.
  * - values
    - map[str, any]
    - **Required.** Pre-configured form values.


.. note::
  The presets serve as a hint for the users only and the use of the
  pre-defined values is not enforced or checked in any way.


=====================
Launching the Project
=====================

Slivka consists of three components: RESTful HTTP server, job 
scheduler (dispatcher) and a simple worker queue running jobs
on the local machine.
The separation allows to run those parts independently of each other.
In situations when the scheduler is down, the server keeps collecting
the requests stashing them in the database, so when the scheduler is working
again it can catch up with the server and dispatch all pending requests.
Similarly, when the server is down, the currently submitted jobs 
are unaffected and can still be processed.

Each component can be started using ``slivka`` executable created during
Slivka package installation.

.. warning:: 
  Before you start, make sure that you have access to the running mongodb
  server which is required but is not part of slivka package.

-----------
HTTP Server
-----------

Slivka server can be started from the directory containing settings file with: 

.. code-block::

  slivka start server --type gunicorn

This will start a gunicorn server, serving slivka endpoints
using default settings specified in the *settings.yaml* file.

A full command line specification is:

.. code-block:: sh

  slivka start [--home SLIVKA_HOME] server \
    [--type TYPE] [--daemon/--no-daemon] [--pid-file PIDFILE] \
    [--workers WORKERS] [--http-socket SOCKET]

.. list-table::
  :header-rows: 1
  :widths: auto
  
  * - Parameter
    - Description
  * - ``SLIVKA_HOME``
    - Path to the configurations directory.
      Alternatively a SLIVKA_HOME environment variable can be set.
      If neither is set, the current working directory is used.
  * - ``TYPE``
    - The wsgi application used to run the server. Currently available
      options are: gunicorn, uwsgi and devel. Using devel is discouraged
      in production as it can only serve one client at the time and may
      potentially leak sensitive data.
  * - ``--daemon/--no-daemon``
    - Whether the process should run as a daemon.
  * - ``PIDFILE``
    - Path to the file where process' pid will be written to.
  * - ``WORKERS``
    - Number of server processes spawned on startup. Not applicable to
      the development server.
  * - ``SOCKET``
    - Specify the socket the server will accept connection from
      overriding the value from the settings file.

If you want to have more control or decided to use different wsgi
application to run the server, you can use *wsgi.py* script provided
in the project directory which contains a wsgi-compatible application
(see `PEP-3333`_).
Here is an alternative way of starting slivka server using gunicorn
(for details how to run the wsgi application with other servers
refer to their respective documentations).

.. code-block:: sh

  gunicorn -b 0.0.0.0:8000 -w 4 -n slivka-http wsgi

---------
Scheduler
---------

Slivka scheduler can be started from the project directory using

.. code-block:: sh

  slivka start scheduler

The full command line specification is:

.. code-block:: sh

  slivka start [--home SLIVKA_HOME] scheduler \
    [--daemon/--no-daemon] [--pid-file PIDFILE]

.. list-table::
  :header-rows: 1
  :widths: auto
  
  * - Parameter
    - Description
  * - ``SLIVKA_HOME``
    - Path to the configurations directory.
      Alternatively a SLIVKA_HOME environment variable can be set.
      If neither is set, the current working directory is used.
  * - ``--daemon/--no-daemon``
    - Whether the process should run as a daemon.
  * - ``PIDFILE``
    - Path to the file where process' pid will be written to.

-----------
Local Queue
-----------

The local queue can be started with ::

  slivka start local-queue

The full command line specification:

.. code-block:: sh

  slivka start [--home SLIVKA_HOME] local-queue \
    [--daemon/--no-daemon] [--pid-file PIDFILE]
 
.. list-table::
  :header-rows: 1
  :widths: auto
  
  * - Parameter
    - Description
  * - ``SLIVKA_HOME``
    - Path to the configurations directory.
      Alternatively a SLIVKA_HOME environment variable can be set.
      If neither is set, the current working directory is used.
  * - ``--daemon/--no-daemon``
    - Whether the process should run as a daemon.
  * - ``PIDFILE``
    - Path to the file where process' pid will be written to.

------------------
Stopping Processes
------------------

To stop any of these processes, send the ``SIGINT`` (2) "interrupt" or
``SIGTERM`` (15) "terminate" signal to the process or press **Ctrl + C**
to send ``KeyboardInterrupt`` to the current process. Avoid using
``SIGKILL`` (9) as killing the process abruptly may cause data
corruption.
