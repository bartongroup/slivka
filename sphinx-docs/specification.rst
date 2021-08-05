*************
Configuration
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

=====================
Service configuration
=====================

Web services can be added to the project by creating service definition
files in the services directory specified in the configuration file
(*services/* by default).
Each service definition is stored in its unique file named
*<service-id>.service.yaml* where the service identifier should be
substituted for the *<service-id>*.
The filename (without the extension) should contain alphanumeric
characters, dashes and underscores only (avoid using spaces) and
will be used as a unique service identifier.
Using lowercase letters is strongly recommended but not required.
Those files store service information, command line
program that will be run, the list of arguments to
that program as well as the additional constraints on those input
parameters.


--------
Metadata
--------

On top of the file there are service metadata, that is, all information
about the service which are not instructions for slivka.
Even though the order in which the keys are defined in the file does
not matter, it's a good practise to place general service information
on top.
Additionally, you can accompany the data with comments (lines starting
with ``#``), although comments are ignored by the program.

Here is the full list of metadata parameters that can be set in the file.

:*slivka-version*:
  The version of slivka this service was written for. It helps
  slivka detect any compatibility issues related to syntax changes.
  For the current version use ``"0.8"``.

:*name*:
  Service name should be concise and self-explanatory. For example,
  indicating the name of the program that it runs.

:*description*:
  *(optional)* Long text which provides additional information about
  the service. It might provide an explanation what the service does
  and how it works.

:*author*:
  *(optional)* One or more authors of the command line program used.

:*version*:
  *(optional)* Version of the command line program. Specifying it
  might prove useful when multiple versions of the same software is
  served. Remember to quote the version number so it's interpreted
  as a string.

:*license*:
  *(optional)* License under which the service or the underlying
  program is used and distributed.

:*classifiers*:
  *(optional)* List of tags that helps users and client software group and
  identify services. The classifiers can be chosen arbitrarily, but
  some client software may rely on those to function properly.

  Example from the clustalw2 service definition:

  .. code-block:: yaml

    classifiers:
    - "Topic : Sequence analysis"
    - "Operation : Multiple sequence alignment"


-------
Command
-------

The rest of the service file contains instructions for slivka how
to run the command line program and what parameters the web service
part should expose to the users.
Let us start with defining the command line program and its arguments
followed by listing the output files.
Then, we use the command arguments to build the parameters for the
web services.
Lastly, we briefly mention available execution methods for job processes.

Base Command
============

The base command (i.e. the program to be run) is specified under the
*command* property. In simple cases this will contain an executable
to be run such as ``clustalw2`` or ``mafft``; however, it is also
possible to name multiple arguments or even insert environment
variables e.g. ``python -m ${HOME}/lib/my-library``. This part will
make the base of our program call and additional arguments will be
appended to that.

If you are concerned about special characters and whitespace and
want to make sure that the command is read properly, you can enumerate
the arguments using a list as shown in the following examples.

.. code-block:: yaml

  command: clustalw2

.. code-block:: yaml

  command: python -m ${HOME}/lib/my-library

.. code-block:: yaml

  command:
  - bash
  - -rx
  - ${SLIVKA_HOME}/bin/my-script.sh

.. note::

  Subprocesses are not executed in the same working directory as slivka,
  so if A program is not accessible from the ``PATH`` an absolute
  path to is must be given. A special ``SLIVKA_HOME`` variable may be
  used to refer to the root directory of the slivka project.

.. warning::

  Never use commands that execute code coming from the users which
  allow script injections. One example is using ``bash -c``.

Arguments
=========

Once the base command is set up, we can move on to enumerating the command
line arguments for the program. Those are placed under the ``args``
property in the service configuration file. It contains an ordered
mapping where each key is a parameter id (we'll need it later)
and values are argument objects with following attributes

:*arg*:
  The argument template which will be inserted into the command.
  Whenever the value for the parameter is not empty, that argument
  is appended to the list of arguments with the actual value
  substituted for the ``$(value)`` placeholder.
  Example: ``--type=$(value)``

  Using environment variables in the argument value is supported.

:*default*:
  *(optional)*
  Value that will be used when no other value was provided for the
  argument. One use is to provide constant values for parameters
  hidden from the front-end users.

:*join*:
  *(optional)*
  Delimiter used to join multiple values for the argument.
  Only applicable to parameters that can take multiple values.
  If *join* is not specified then the argument is repeated multiple
  times for each value. For example, for two values ``alpha``, ``bravo``

  .. code-block:: yaml

    arg: -p $(value)

  will result in command arguments ``-p alpha -p bravo``, but

  .. code-block:: yaml

    arg: -p $(value)
    join: ","

  will result in ``-p alpha,bravo``.

  .. note:: Since arguments splitting happens before interpolation,
    using space as the delimiter produces single argument.
    In the example above, it would result in ``-p "alpha bravo"``
    not ``-p alpha bravo``.

:*symlink*:
  *(optional)*
  Instructs slivka to create symbolic link to the file in the process'
  working directory. Only applicable to parameters that take files
  as an input. When *symlink* is present, the value of the parameter
  will be replaced by the symlink name pointing to the original path.


---------------------
Environment variables
---------------------

If the program you wrap needs specific environment variables or
you need to adjust existing variables they can be specified under
the *env* property. It should contain a mapping where each key
is a variable name that will be set to its corresponding value
when starting the command. The value can contain current environment
variables which are included using ``${VARIABLE}`` syntax. Although
any system variable can be used, references to other variables
defined in this mapping will not work.

Slivka executes each program in a new environment removing all
variables other than ``PATH`` and ``SLIVKA_HOME`` and setting new
variables from *env*. If you want any system variable to be passed
to the new process, you need to re-define it here.

Example:

.. code-block:: yaml

  env:
    PATH: ${HOME}/bin:${PATH}  # extend the existing PATH
    PYTHON: /usr/bin/python3.8  # define new variable
    PYTHONPATH: ${PYTHONPATH}  # pass the existing variable


.. _parameters specification:

----------------
Input parameters
----------------

The input parameters defined under *parameters* property list all
the variables that the users will be able to adjust when submitting
their jobs. Those are closely linked to the command line arguments,
in fact, they are the bridge between the front-end users and the
command line arguments.

Input *parameters* is a mapping just like command *args* where
each key is the parameter id and value is an object describing the
parameter. The ids of the parameters should match those of the
command line arguments defined in the previous section. The values
passed to the parameters by the user will be validated and passed to their
corresponding arguments.Not every argument has to have corresponding
input parameter; in such case the value for the argument will always
be empty and the argument will be skipped unless a default (constant)
is set. However, every input parameter needs to have corresponding
command line argument.

As mentioned before, input parameters is a mapping under the *parameters*
property where each key is the parameter identifier and each value is
an object defining the parameter having the following attributes
(which are optional unless stated otherwise):

:*name*:
  *(required)*
  Name of the parameter. Should be concise and self-explanatory.

:*description*:
  Longer description of the parameter containing details about
  its function.

:*type*:
  *(required)*
  Type of the parameter, determines validation functions used on
  the value and additional constraints that may be imposed.
  Built-in types include ``integer``, ``decimal``, ``text``,
  ``flag``, ``choice`` and ``file``; however, a path to the custom
  implementation of the type can be used as well (defining custom types
  will be covered in advanced usage tutorial).
  Type name can be immediately followed by a pair of square brackets
  to convert in into an array variant e.g. ``text[]``.

:*default*:
  Value that will be used when user leaves the parameter empty.
  Default value must meet all the type constraints and must be
  an array for array types.

:*required*:
  Determines whether the value for this parameter is required.
  Allowed values are ``yes`` and ``no``.
  All parameters are required by default but specifying default value
  nullifies the requirement.

:*condition*:
  Mathematical/logical expression involving other parameters
  that allows to conditionally disable the parameter or restrict
  allowed values. Usage, syntax and limitations will be covered in
  the advanced usage tutorial.

Those properties are always present regardless of the parameter
type. However, individual types allow extra attributes and value constraints.
The additional constraints are identical for the array type and are
evaluated for each value individually.

Integer type
============

:*min*:
  Integer. Minimum allowed value (inclusive), unbound if not present.

:*max*:
  Integer. Maximum allowed value (inclusive), unbound if not present.

Decimal type
============

:*min*:
  Float. Minimum value, unbound if not present.

:*min-exclusive*:
  Boolean. Whether the minimum is exclusive (inclusive by default).

:*max*:
  Float. Maximum value, unbound if not present.

:*max-exclusive*:
  Boolean. Whether the maximum is exclusive (inclusive by default).

Text type
=========

:*min-length*:
  Integer. Minimum length of the text.

:*max-length*:
  Integer. Maximum length of the text.

Choice type
===========

:*choices*:
  Mapping of string to string. Contains the available choices -- keys
  and the values they are mapped to. The mapping allows to hide the
  actual command line arguments and display more meaningful names
  for the choices.

File type
=========

:*media-type*:
  String. Checks the file content to be of the specified type. Media type
  format follows `RFC 2045`_. Currently supported types include
  plain text, json, yaml and bioinformatic data types which require
  biopython to be installed.

:*media-type-parameters*:
  Array of strings. Additional hints following the base media type.
  Those are not used for value validation and serve solely as hints
  for the users and client applications.

:*default*:
  Default value is not currently allowed for the file type and setting
  it will result in an error.

.. _RFC 2045: https://datatracker.ietf.org/doc/html/rfc2045

-------
Outputs
-------

Once the process completes and creates the output files, users
need to be able to retrieve them. For that, they need to be listed
under the *outputs* property of the file. This, again, is a mapping
where each key is an item identifier and values are objects that
define output files shown to the users. Each output file object
has following properties:

:*path*:
  *(required)* String.
  Path or a glob_ pattern that will be used to match files
  in the directory where the process was run. No files outside
  the working directory will be matched.
  Glob pattern can be particularly useful if the program produces
  multiple files that can be grouped together.
  Additionally, standard output and error streams are automatically
  redirected to the ``stdout`` and ``stderr`` files.

  .. note:: Patterns starting with a special characters must be quoted.

:*media-type*:
  *(optional)* String.
  Media type of the output file using `RFC 2045`_ format.
  Serves informative purpose only.

.. _glob: https://en.wikipedia.org/wiki/Glob_(programming)

Example: 

.. code-block:: yaml
    
  log:
    path: stdout
  output:
    path: output.txt
    media-type: text/plain
  auxiliary:
    path: aux_*.json
    media-type: application/json

    
.. _execution management:

--------------------
Execution management
--------------------

So far, we instructed slivka how to construct the command line arguments
for the program and what input parameters the web service wrapper should 
present to the users.
The remaining piece is execution of the command on the operating system.
This role is fulfilled by the Runners which are configured under
the *execution* property of the service file.

Runners in slivka are classes that implement methods for starting the
command on the system and watching the completion of the process.
They are links between the abstract job and
the actual process running on the system.
Currently, there are three runner types that realise process execution
in three distinct ways.

- ``ShellRunner`` the simplest of all three. Runs the command as
  a subprocess in the current shell. Doesn't require any prior setup
  but is only suitable for a very small workloads since spawning many
  computationally-heavy processes can easily clog the operating system.
  We do no recommend using it in production.

- ``SlivkaQueueRunner`` is an improvement of the shell runner which delegates
  process execution to a separate slivka queue. The queue is better
  suited for handling multiple jobs and can limit the number of simultaneous
  workers to preserve system resources. It requires running local-queue
  process to work.

  Parameters:

  :*address*:
    The address of the queue server if different than the one listed in the
    main configuration file.

- ``GridEngineRunner`` uses a third-party Altair Grid Engine
  (formerly Univa Grid Engine) to run the jobs using ``qsub`` command.
  It allows for much more sophisticated resource management capable
  of serving thousands of jobs. It requires the Grid engine to be
  available on your system, however.

  Parameters:
  
  :*qargs*:
    List of arguments that will be placed directly after ``qsub`` command.
    The runner provides ``-V -cwd -o stdout -e stderr`` arguments implicitly
    and those should not be overridden.
    The arguments can be a string or an array of strings.

The *execution* property can have two sub-properties under it:
*runners* and *selector*.

Runners
=======

Similarly to other values in this configuration file, *runners* contains
a mapping of runner ids to runner objects. You can specify multiple
runners, however, if the selector is not set, the one named ``default``
will be always used. Each runner object has following properties:

:*type*:
  Type of the runner which is either a class name of one of the
  built-in runners or a path to the custom class implementing Runner
  interface. Creating custom runners will be covered in advanced usage
  guide. Available Built-in runners are: ``ShellRunner``,``SlivkaQueueRunner``
  and ``GridEngineRunner``.

:*parameters*:
  Extra parameters that will be passed to the runner's constructor
  as keyword arguments.

Selector
========

The main idea behind having multiple runners is that depending on
the size of the job, we can decide how much resources we want to allocate
to execute it.
Selector is a Python function which, given the input parameters,
can decide and return the identifier of the runner suitable for
this job. It can also decide the job to be rejected based on the
parameters.
You can choose your own selector by setting the value of *selector*
property to the path to the python function.
The default selector (if unset) always chooses the *"default"* runner.


======================
Command line interface
======================

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

Slivka server can be started from the directory containing configuration file with:

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
