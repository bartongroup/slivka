*************
Configuration
*************

This page provides a technical specification of the configuration
files used by slivka. It describes the structure of the main
configuration file and service definitions.

=================
Project Structure
=================

New slivka projects initialized by the :program:`slivka init` command
start with the following directory structure::

  <project-root>/
  ├── config.yaml
  ├── manage.py
  ├── wsgi.py
  ├── scripts/
  │  ├── example.py
  │  └── selectors.py
  ├── services/
  │  └── example.service.yaml
  └── static/
     ├── openapi.yaml
     └── redoc-index.html

The topmost directory in the structure, one containing a
:file:`config.yaml` file is a project root or project home directory.
The collection of configuration files in that directory used by slivka
is referred to as a slivka project. The directory contains several
files essential for the operation of the slivka application.

:config.yaml:
  The main configuration file required for the proper functioning of
  slivka. Typically, slivka recognises the project directory as the
  one containing this file. It can alternatively be named
  *settings.yaml* and either *.yaml* or *.yml* extension is allowed.
  Detailed information about the file syntax and parameters is
  provided in the `configuration file`_ section.
:wsgi.py:
  A python module file containing a WSGI-compatible application as
  specified by `PEP-3333`_. This file is used by a WSGI middleware to
  serve slivka HTTP endpoints. The WSGI servers may load this module
  directly instead of launching the server through the
  :program:`slivka` command.
:manage.py:
  A legacy executable script which was used to start slivka in this
  project directory. Its functionality was fully replaced by the
  :program:`slivka` command. You should not edit this file.
:scripts/:
  A directory containing auxiliary script files. Its presence is not
  required and it only contains files required by the example service.
:services/:
  A directory containing service configuration files. Each file in
  this directory whose name matches :file:`{service-id}.service.yaml`
  pattern is used to load service definitions. The directory can be
  changed in the main configuration file under the
  ``directory.services`` property.
  It comes with an example service in the :file:`example.service.yaml`
  which teaches you how to construct services and can be used as a
  template for creating new ones.
:static/:
  A directory containing static files used by the HTTP server.
  Currently, it contains two files needed to render the API
  documentation page. The :file:`openapi.yaml` file stores the
  `OpenAPI 3.0.3`_ specification which is rendered by the Redoc_
  documentation generator from the :file:`redoc-index.html` file. You
  are free to edit those files according to your needs. If slivka
  fails to find those files in the project directory, it uses default
  versions from its package resources.

.. _`PEP-3333`: https://www.python.org/dev/peps/pep-3333/
.. _`OpenAPI 3.0.3`: https://swagger.io/specification/
.. _Redoc: https://github.com/Redocly/redoc

All the configuration files are text files written in `YAML
<https://yaml.org/>`_ and can be edited with any text editor.

It's not advisable to edit *manage.py* and *wsgi.py* scripts unless
you are an advanced user and you know what you are doing.

.. _specification-config-file:

==================
Configuration file
==================

*config.yaml* is the main configuration file of the project that
stores variables used across the application. The properties in the
file can be structured as a tree or a flat mapping as shown in the
following snippets. Both forms are equivalent.

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
  A version of the configuration file syntax used to check for project
  compatibility. For the current slivka version, this must be set to ``"0.3"``.

..

:*directory.uploads*:
  Path to a directory where the user-uploaded files will be stored.
  Relative paths are resolved with respect to the project root
  directory. It's recommended to set up the proxy server to serve
  those files directly, i.e. under */uploads* path (configurable
  by changing ``server.uploads-path``).
  The default is ``"./media/uploads"``.

:*directory.jobs*:
  Path to a directory where the job directories will be created. For
  each job, slivka creates a sub-directory in that folder and sets it
  as a current working directory for that process. A relative path is
  resolved with respect to the project directory. The job directories
  contain output files which are served to the front-end users. It's
  recommended to set up the proxy server to serve those files
  directly, i.e. under */jobs* path (configurable by changing
  ``server.jobs-path``). The default is ``"./media/jobs"``

:*directory.logs*:
  Path to a directory where the log files will be created.
  The default is ``"./logs"``

:*directory.services*:
  Path to a directory containing service definition files. Slivka
  automatically finds and loads service definitions from files under
  this directory whose names match :file:`{service-id}.service.yaml`
  pattern. The default is ``"./services"``

..

:*server.host*:
  Address and port under which a slivka application is hosted.
  It's highly recommended to run slivka behind an HTTP proxy server
  such as `nginx`_, `Apache HTTP Server`_ or `lighttpd`_,
  so no external traffic connects to the WSGI server directly.
  Set the value to the address where the proxy server connectS from or
  ``0.0.0.0`` to accept connections from anywhere (not recommended).
  The default is ``127.0.0.1:4040``.

:*server.uploads-path*:
  The path where the uploaded files are served at. It should be set to
  the same path that the proxy server uses to serve files from the
  uploads directory (set in the *directory.uploads* parameter).
  The default is ``"/media/uploads"``.

:*server.jobs-path*:
  The path where the job results are served at. It should be set to the
  same path that the proxy server uses to serve files from the
  jobs directory (set in *directory.jobs* parameter).
  The default is ``"/media/jobs"``.

:*server.prefix*:
  *(optional)* The URL path at which the proxy server serves the WSGI
  application if it's other than the root. This is needed for the URLs
  and redirects to work properly. For example, if you configured your
  proxy server to redirect all requests starting with */slivka* to the
  application, then set the prefix value to ``/slivka``.

  .. note::

    Configure your proxy rewrite rule to **not** remove the prefix
    from the URL.

.. _nginx: https://nginx.org/
.. _Apache HTTP Server: https://httpd.apache.org/
.. _lighttpd: https://www.lighttpd.net/

:*local-queue.host*:
  Host and port where the local queue server will listen to commands on.
  Use a localhost address or a named socket that only trusted users
  (i.e. slivka) can write to.
  You may specify the protocol ``tcp://`` explicitly for TCP connections.
  The ``ipc://`` or ``unix://`` protocol must be specified when using
  named sockets.
  The default is ``tcp://127.0.0.1:4041``.

  .. warning::

    NEVER ALLOW UNTRUSTED CONNECTIONS TO THAT ADDRESS. It allows
    sending and executing an arbitrary code by the queue.

..

:*mongodb.host*:
  *(optional)* Address and port of the mongo database that slivka will connect to.
  Either this or *mongodb.socket* parameter must be present.
  The default is ``127.0.0.1:27017``.

:*mongodb.socket*:
  *(optional)* Named socket where mongo database accepts connections at.
  Either this or *mongodb.host* parameter must be present.

:*mongodb.username*:
  *(optional)* A username that the application will use to log in to the
  database. A default user will be used if not provided.
  The default is unset.

:*mongodb.password*:
  *(optional)* A password used to authenticate the user when connecting
  to the database. The default is unset.

:*mongodb.database*:
  Database that will be used by the slivka application to store data
  for that project. The default is ``slivka``

=====================
Service configuration
=====================

Web services can be added to the project by creating service
definition files in the services directory specified in the
configuration file (:file:`services/` by default). Each service
definition must be stored in its unique file named
:file:`{service-id}.service.yaml` where the service identifier should
be substituted for the *service-id*. The service identifier, and hence
the filename should contain alphanumeric characters, dashes and
underscores only (avoid using spaces). Using lowercase letters is
strongly recommended but not required. Slivka creates a single service
for each service file found. A quick overview of the service
definition file and an example service is provided in the
:ref:`getting-started-example-service` section.

The configuration file is a YAML document organised into a tree.
Several properties are placed at the top level of the document
tree and contain simple values. Others may contain complex objects
making a nested document structure. The ordering of the top-level keys
is irrelevant, but nested objects do respect the order of the keys.

--------
Metadata
--------

Service metadata is typically placed on top of the file. It contains
information about the service which is displayed to the front-end
users. Even though the order of the top-level keys in the file is not
significant, it's convenient to put service metadata first.
Additionally, lines starting with a hash sign ``#`` are comments and
are ignored by the program. They can be useful for adding auxiliary
information about the configuration for maintenance purposes.

Here is the full list of metadata parameters that should be defined
at the top level of the document tree.

:*slivka-version*:
  *(string)* The version of slivka this service was written for. It
  helps slivka detect any compatibility issues related to syntax
  changes. Remember to quote the version number, so it's interpreted
  as a string and not a float. For the current version use ``"0.8.3"``.

:*name*:
  *(string)* Service name as displayed to users. It should be concise
  and self-explanatory. For example, the name of the underlying
  program or tool run by the service.

:*description*:
  *(string) (optional)* Long text providing users with additional
  information about the service. It might include an explanation of
  what the service does and how it works.

:*author*:
  *(string) (optional)* One or more authors of the command line
  program run by the service.

:*version*:
  *(string) (optional)* Version of the command line program run by the
  service. Specifying the version might be useful when multiple versions
  of the tool are provided as web services. Remember to quote the
  version number so it's interpreted as a string and not float.

:*license*:
  *(string) (optional)* The name of a license under which the service
  or the underlying program is distributed.

:*classifiers*:
  *(array[string]) (optional)* List of tags that help users and client
  software group and identify services. The classifiers can be chosen
  arbitrarily, but some client software may rely on those to function
  properly.

  Example from the clustalw2 service definition:

  .. code-block:: yaml

    classifiers:
    - "Topic : Sequence analysis"
    - "Operation : Multiple sequence alignment"


-------
Command
-------

The following configuration contains instructions for slivka on how to
build the list of arguments for the command line program. The command
line configuration consists of four parts, the base command which
invokes the program, the list of arguments appended to it, the
environment variables and the list of output files produced by the
tool.

Base Command
============

The base command (i.e. the program to be run) is specified under the
*command* property. A string or an array of strings are accepted
values. In simple cases the command contains an executable to be run
such as ``clustalw2`` or ``mafft``; however, it is also possible to
name multiple arguments that make up the command running the program
or even insert environment variables e.g. ``python -m
${HOME}/lib/my-library``. This part makes the base of the program call
and additional arguments are appended to that. If the arguments are
given as an array, the environment variables are interpolated first
and the result is processed in a similar way to the ``execl``
function. If given as a string, they are split into a list of arguments
using :py:func:`shlex.split` first.

If you are concerned about special characters and whitespaces and want
to make sure that the command is parsed properly, you can enumerate
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
  therefore if a program is not accessible from the ``PATH``, an absolute
  path must be used. The command may include ``$SLIVKA_HOME`` variable
  containing the absolute path to the root directory of the slivka project.

.. warning::

  Never use commands that execute code coming from the users which
  allow script injections. One example is using ``bash -c``.

Arguments
=========

Once the base command is set up, you should enumerate the remaining command
line arguments of the program. Those are placed under the *args*
property in the service configuration file. It contains an ordered
mapping where each key is a parameter id (we'll need it later)
and values are argument objects with the following attributes

:*arg*:
  *(string)* The template for arguments that will be inserted into the
  command. Whenever the value for the parameter is not empty, that
  argument is appended to the list of arguments with the actual value
  substituted for the ``$(value)`` placeholder. Example:
  ``--type=$(value)``

  The argument template may include system environment variables as
  well as those defined in this file under an *env* property.
  The variables are inserted using shell syntax ``${VARIABLE}``
  or a short notation ``$VARIABLE``. The variables are interpolated
  before the command is split into individual arguments.

:*default*:
  *(string) (optional)* Value that will be inserted into the template
  when no value is provided for the argument. You can use it to
  provide constant values for parameters hidden from front-end users.

:*join*:
  *(string) (optional)* Delimiter used to join multiple values. Only
  applicable to array-type parameters. If *join* is not specified,
  then the multi-valued arguments are repeated for each value. For
  example, for two values ``alpha`` and ``bravo``

  .. code-block:: yaml

    arg: -p $(value)

  will result in the command line arguments ``-p alpha -p bravo``, but

  .. code-block:: yaml

    arg: -p $(value)
    join: ","

  will result in ``-p alpha,bravo``.

  .. note::
    Arguments splitting happens before interpolation. Using
    space as the delimiter produces a single argument. In the example
    above, it would result in ``-p "alpha bravo"`` not ``-p alpha bravo``.

:*symlink*:
  *(string) (optional)*
  Instructs slivka to create a symbolic link to the file in the process'
  working directory. Only applicable to file-type parameters.
  When *symlink* is present, the value of the parameter
  will be replaced by the symlink name.

Environment variables
=====================

If the program you wrap needs specific environment variables or
you need to adjust existing variables you can specify them under
the *env* property. It should contain a mapping where each key
is a variable name that will be set to its corresponding value
when starting the command. The value can contain current environment
variables which are included using ``${VARIABLE}`` syntax. Although
any system variable can be used, references to other variables
defined in this mapping will not be resolved to avoid issues with
circular variable definitions.

Slivka executes each program in a new environment removing all
variables other than ``PATH`` and ``SLIVKA_HOME`` and then adding the
variables defined in *env*. If you want any system variable to be passed
to the new process, you need to redefine it here.

Example:

.. code-block:: yaml

  env:
    PATH: ${HOME}/bin:${PATH}  # extend the existing PATH
    PYTHON: /usr/bin/python3.8  # define new variable
    PYTHONPATH: ${PYTHONPATH}  # pass the existing variable


Outputs
=======

To make process output files retrievable by users they need
to be listed in the configuration file under the *outputs* property.
It contains a mapping where each key is an item identifier and values
are objects describing service outputs. Each object has tmhe following
properties:

:*path*:
  *(string) (required)* Path or a glob_ pattern that will be used to
  match output files in the process' working directory. Only the
  working directory and directories below are searched recursively. No
  files outside the working directory will match the pattern. Glob
  patterns can be used to capture multiple output files that can be
  grouped together. Standard output and error streams are
  automatically redirected to the ``stdout`` and ``stderr`` files
  and can be referred to by those names.

  .. note:: Patterns starting with a special character must be quoted.

:*name*:
  *(string) (optional)* Name of the result that will be displayed to
  users. Serves informational purposes and doesn't have to match the
  file name.

:*media-type*:
  *(string) (optional)*. The media type of the output file using `RFC
  2045`_ format. Serves informational purposes only. Slivka does not
  verify if the actual media type of the output file matches the
  declared type.

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


.. _parameters specification:

----------------
Input parameters
----------------

The input parameters defined under *parameters* property list all
the variables that the users will be able to adjust when submitting
their jobs. Those are closely linked to the command-line arguments
they are the bridge between the front-end users and the
command-line arguments.

Input *parameters* key contains a mapping just like command *args* where
each key is the parameter id and value is an object describing the
parameter. The ids of the parameters should match those of the
command line arguments defined in the previous section. The values
passed to the parameters by the user will be validated and passed to their
corresponding arguments. Not every argument has to have a corresponding
input parameter; in such cases, the value for the argument will always
be empty and the argument will be skipped unless a default (constant)
is set. However, every input parameter needs to have a corresponding
command line argument.

As mentioned before, input parameters is a mapping under the *parameters*
property where each key is the parameter identifier and each value is
an object defining the parameter having the following attributes
(which are optional unless stated otherwise):

:*name*:
  *(required)*
  A name of the parameter. Should be concise and self-explanatory.

:*description*:
  A longer description of the parameter containing details about
  its function.

:*type*:
  *(required)*
  The type of the parameter determines validation functions used on
  the value and additional constraints that may be imposed.
  Built-in types include ``integer``, ``decimal``, ``text``,
  ``flag``, ``choice`` and ``file``; however, a path to the custom
  implementation of the type can be used as well (defining custom types
  will be covered in the advanced usage tutorial).
  Type name can be immediately followed by a pair of square brackets
  to convert it into an array variant e.g. ``text[]``.

:*default*:
  A value that will be used when users leave the parameter empty.
  The default value must meet all the type constraints and must be
  an array for array types.

:*required*:
  Determines whether the value for this parameter is required.
  Allowed values are ``yes`` and ``no``.
  All parameters are required by default but specifying a default value
  nullifies the requirement.

:*condition*:
  Mathematical/logical expression involving other parameters that
  allows to conditionally disable the parameter or restrict allowed
  values. Usage, syntax and limitations will be covered in the
  :ref:`advanced-usage-conditions` section in the advanced usage
  tutorial.

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
  and the values they are mapped to. The mapping allows hiding
  actual command line arguments and displaying more meaningful names
  for the choices.

File type
=========

:*media-type*:
  String. Checks if the file content is of the specified type. Media type
  format follows `RFC 2045`_. Currently supported types include
  plain text, json, yaml and bioinformatic data types which require
  biopython to be installed.

:*media-type-parameters*:
  An array of strings. Additional hints following the base media type.
  Those are not used for value validation and serve solely as hints
  for the users and client applications.

:*default*:
  The default value is not currently allowed for the file type and setting
  it will result in an error.

.. _RFC 2045: https://datatracker.ietf.org/doc/html/rfc2045


.. _execution management:

--------------------
Execution management
--------------------

So far, we instructed slivka on how to construct the command line arguments
for the program and what input parameters the web service wrapper should
present to the users.
The remaining piece is the execution of the command on the operating system.
This role is fulfilled by the Runners which are configured under
the *execution* property of the service file.

Runners in slivka are classes that implement methods for starting the
command on the system and watching the completion of the process.
They are links between the abstract job and
the actual process running on the system.
Currently, four built-in runner types realise realise process execution
in four distinct ways.

The *execution* property contains two sub-properties: *runners* and
*selector*. The *runners* property defines a list of runners available
to run jobs for this service. The *selector* property contains a path
to a special selector function which chooses the runner based on the
input parameters.

Runners
=======

Similarly to other values in this configuration file, *runners*
contains a mapping of runner ids to runner objects. You can specify
multiple runners, however, if the selector is not set, the one named
``default`` will be always used. Each runner object has the following
properties:

:*type*:
  Type of the runner which is either a class name of one of the
  built-in runners or a path to the custom class implementing Runner
  interface. Creating custom runners will be covered in the advanced
  usage guide. Available Built-in runners are ``ShellRunner``,
  ``SlivkaQueueRunner``, ``GridEngineRunner``, ``SlurmRunner``,
  and ``LSFRunner``.

:*parameters*:
  Extra parameters that will be passed to the runner's constructor
  as keyword arguments.

- ``ShellRunner`` is the simplest of all three. Runs the command as
  a subprocess in the current shell. Doesn't require any prior setup
  but is only suitable for very small workloads since spawning many
  computationally-heavy processes can easily clog the operating system.
  We do not recommend using it in production.

- ``SlivkaQueueRunner`` is an improvement of the shell runner which delegates
  process execution to a separate slivka queue. The queue is better
  suited for handling multiple jobs and can limit the number of simultaneous
  workers to preserve system resources. It requires running a local-queue
  process to work.

  Parameters:

  :*address*:
    The address of the queue server if it is different than the one listed in the
    main configuration file.

- ``GridEngineRunner`` uses a third-party `Altair Grid Engine`_
  (formerly Univa Grid Engine) to run the jobs using a :program:`qsub` command.
  It allows for much more sophisticated resource management capable
  of serving thousands of jobs. It requires the Grid engine to be
  available on your system, however.

  Parameters:

  :*qargs*:
    List of arguments that will be placed directly after :program:`qsub` command.
    The runner provides ``-V -cwd -o stdout -e stderr`` arguments implicitly
    and those should not be overridden.
    The arguments can be a string or an array of strings.

- ``SlurmRunner`` uses a third-party `Slurm Workload Manager`_ to run
  the processes. The command line programs are wrapped in bash scripts
  and launched with a :program:`sbatch` command. This solution allows
  advanced resource management on distributed computing systems
  running many jobs simultaneously. It requires Slurm to be installed
  on your system.

  Parameters:

  :*sbatchargs*:
    List of arguments appended to the :program:`sbatch` command that
    control execution parameters. The runner provides
    ``--output=stdout --error=stderr --parsable`` arguments implicitly
    which should not be overridden. The arguments can be provided
    as an array of strings or as a string, in which case they will be
    split into an array with :py:func:`shlex.split` function.

  .. versionadded:: 0.8.1b0
    Introduced Slurm runner

- ``LSFRunner` uses the third-party `IBM Spectrum LSF`_ to run jobs
  via the :program:`bsub` command.  This solution allows many jobs to
  be run on large compute clusters.  It requires LSF to be installed on
  your system.

  Parameters:

  :*bsubargs*:
    List of arguments appended to the :program:bsub: command that control
    execution parameters.  The runner always provides ``-o`` and ``-e``
    arguments, which should not be overridden.  The arguments can be 
    provided as an array of strings or as a string, in which case they
    will be split with :py:func:`shelx.split`.

  .. versionadded:: 0.8.3b0
    Introduced LSF runner

.. _`Altair Grid Engine`: https://www.altair.com/grid-engine
.. _`Slurm Workload Manager`: https://slurm.schedmd.com/
.. _`IBM Spectrum LSF`: https://www.ibm.com/docs/en/spectrum-lsf/

Selector
========

A selector is a Python function that given the input parameters can
choose a runner suitable for the job. It allows you to pick
runners allocating different amounts of resources appropriate for
the size of the job. The *selector* property contains a path to a
callable that accepts a mapping of parameter ids to argument values
and returns an id of a runner.

Declaring the selector is required if you want to use more than one
runner. A default selector (if unset) always chooses the runner named
*default*.

.. _`specification:Tests`:

-----
Tests
-----

.. versionadded:: 0.8.3

In slivka, you can define a series of service tests that are run every
hour to assess the availability of each runner. The status of the last
executed test is accessible to the users through the REST API and lets
them see the current availability of the services.

The tests are defined under the *tests* property and should contain
a list of objects with the following properties:

:*applicable-runners*:
  This is the list of runner names that this test is applied to.
  Currently, having more than one test for a single runner may produce
  inconsistent results depending on the test execution order.
  This issue will be addressed in the future.

:*parameters*:
  It contains the parameters that are provided to the runner during the
  test. The object keys correspond to argument names given in the *args*
  section and the values are the command values.
  Unlike user inputs, those values are not passed through the validation
  and conversion process and are passed to the command line unchanged,
  so make sure the values are valid and complete.
  Only strings or lists of strings are allowed. You can insert environment
  variables using shell syntax for variables (``$VAR`` or  ``${VAR}``) and
  they will be expanded.

:*timeout* (optional):
  You may specify the timeout for the tests. It's a number of seconds after
  which the tests will be stopped and result in a *WARNING* status.
  The timeout defaults to 15 minutes if not specified.

*Example:*

.. code-block:: yaml

  tests:
  - applicable-runners:
    - default
    - local
    parameters:
      input-file: "$SLIVKA_HOME/testdata/example-input.txt"
      count: "5"
      args:
      - "placeholder0"
      - "placeholder1"
      - "placeholder2"
    timeout: 150

======================
Command line interface
======================

Slivka consists of three components: RESTful HTTP server, job
scheduler (dispatcher) and a simple worker queue running jobs
locally.
The separation allows running those parts independently of each other.
In situations when the scheduler is down, the server keeps collecting
the requests and stashing them in the database, so when the scheduler is working
again it can catch up with the server and dispatch all pending requests.
Similarly, when the server is down, the currently submitted jobs
are unaffected and can still be processed.

Each component can be started using the :program:`slivka` executable
created during the slivka package installation.

.. warning::
  Before you start slivka, make sure that you have access to the
  running MongoDB server which is required but is not the part of the
  slivka package.

-----------
HTTP Server
-----------

Slivka server can be started from the directory containing the configuration
file with:

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
      Alternatively, a SLIVKA_HOME environment variable can be set.
      If neither is set, the current working directory is used.
  * - ``TYPE``
    - The WSGI application used to run the server. Currently available
      options are gunicorn, uwsgi and devel. Using devel is discouraged
      in production as it can only serve one client at the time and may
      potentially leak sensitive data.
  * - ``--daemon/--no-daemon``
    - Whether the process should run as a daemon.
  * - ``PIDFILE``
    - Path to the file where process' pid will be written to.
  * - ``WORKERS``
    - The number of server processes spawned on startup. Not applicable to
      the development server.
  * - ``SOCKET``
    - Specify the socket the server will accept connection from
      overriding the value from the settings file.

If you want to have more control or decided to use a different WSGI
application to run the server, you can use *wsgi.py* script provided
in the project directory which contains a WSGI-compatible application
(see `PEP-3333`_).
Here is an alternative way of starting the slivka server using gunicorn
(for details on how to run the WSGI application with other servers
refer to their respective documentation).

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
      Alternatively, a SLIVKA_HOME environment variable can be set.
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
    [--address ADDR] [--workers WORKERS] \
    [--daemon/--no-daemon] [--pid-file PIDFILE]

.. list-table::
  :header-rows: 1
  :widths: auto

  * - Parameter
    - Description
  * - ``SLIVKA_HOME``
    - Path to the configurations directory.
      Alternatively, a SLIVKA_HOME environment variable can be set.
      If neither is set, the current working directory is used.
  * - ``ADDR``
    - Address the queue server will bind to. Overrides the value
      from the configuration file.
  * - ``WORKERS``
    - Maximum number of workers that will handle jobs simultaneously.
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
