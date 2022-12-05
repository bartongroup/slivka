***************
Getting Started
***************

This page will provide you with a basic introduction to slivka.
You will learn how to create and run a slivka project, configure
web services and access them from the web using curl.
First, follow the :doc:`installation` instructions to install slivka
and proceed to the following sections in this document.

=====================
A Minimal Application
=====================

Slivka does not provide any web services out of the box, it is a
framework that allows you to turn command-line tools into services.
Before you can start hosting the web services, you must create a new
slivka project. The project is a collection of configuration files
containing slivka settings and service definitions, and, optionally,
scripts and binary files. In order to set up a new project, navigate
to a directory where you want to create a new project and run ::

  slivka init my-slivka-project

This command will create a new directory named
:file:`my-slivka-project` and copy the essential project files into
it. You may change the name of the project directory or use ``.`` to
install the files directly in the current directory.

In this documentation, we refer to the topmost project directory
(:file:`my-slivka-project` in this example) as a project root or
project home directory. This is the directory containing the
:file:`config.yaml` file and it is typically a working directory of a
*slivka* process. All relative paths are resolved relative to this
directory.

To run the application, navigate into the project root directory and
start three slivka processes in the background: server, scheduler and
local-queue (make sure that the MongoDB is already running). ::

  slivka start server &
  slivka start scheduler &
  slivka start local-queue &

Once they are running, slivka is ready to accept and process incoming
job requests. You can see that the server is up by visiting
`<http://127.0.0.1:4040/api/version>`_. The page should display the
current version of the slivka framework and API. You can stop the
processes by sending an INTERRUPT signal or pressing :kbd:`Control-C`
when the process is in the foreground.

.. note::

  If your MongoDB is listening on a port other than the default
  or any of the ports used by slivka are already in use you can
  change them in the *config.yaml* file.

===================
Structure of Slivka
===================

Before we dive into the details of writing web services, we should
briefly understand how slivka is organised with the help of a diagram.

.. figure:: overview.svg

At the front of the application, there is a REST server that provides
an interface to communicate with slivka from the web. Clients can talk
to the server over HTTP to send new jobs, query running jobs status or
request output files. The server stashes all job requests in the
database to be picked up by the scheduler.

The scheduler is the heart of the application. It is responsible for
processing job requests, combining parameters into command-line
arguments and dispatching jobs to execution systems. It collects job
requests from the Mongo Database and dispatches them to the available
execution systems. It continuously monitors the jobs and updates their
status in the database.

The scheduler maintains one or more runners for each installed
service. The runners are interfaces between the scheduler and
workload managers or an operating system. They contain instructions on
how to execute command line programs provided by the scheduler
and monitor their status.

If you do not use advanced workload managers on your system, slivka
comes with a simple worker queue process which spawns job processes
locally.

-------------------
Configuration files
-------------------

The configuration files live outside the slivka library inside the
project directory. They supply variables to slivka which are located
in the :file:`config.yaml` file and provide web service definitions
specified in the :file:`{service_name}.service.yaml` files inside the
:file:`services` directory. Additionally, you may include custom
scripts, binaries and static files inside the project to be used by
that slivka instance. This way you can have multiple projects set up
on a single machine each having individual configurations and
services.

As a system administrator, you are responsible for writing and
maintaining those configuration files. Therefore, the rest of this
tutorial focuses on the configuration files.

-------------------
Directory Structure
-------------------

New slivka projects created by :program:`slivka init` are initialized
with the following directory structure:

| <project-root>/
| ├── config.yaml
| ├── manage.py
| ├── scripts/
| │   ├── example.py
| │   └── selectors.py
| ├── services/
| │   └── example.service.yaml
| ├── static/
| │   ├── openapi.yaml
| │   └── redoc-index.html
| └── wsgi.py

The starting point of the configuration is the :file:`config.yaml`
file. It provides important parameters needed to start slivka and
is the first file slivka searches for on startup.
The variables contained in the file allow you to control the
structure of directories used by slivka, server addresses and
database connection.
The structure of the configuration file is explained in detail
on the :doc:`/specification` page.

.. TODO: link to specification section

New projects come with an example service which can be used as a base
for creating other services. The command line program this service
runs is an :file:`example.py` Python script located in the
:file:`scripts` directory. The service configuration is located in the
:file:`services/example.service.yaml` file. Slivka searches for
service definitions in files under the :file:`services` directory
whose name match :file:`{service_id}.service.yaml` pattern. That
directory may be changed in the main configuration file. For each
service file found, slivka instantiates a single web service. There is
no upper limit to the number of services hosted by a single slivka
instance as long as their identifiers are unique.

The service definitions may be accompanied by a selector script. The
example service uses a function from the :file:`scripts/selectors.py`
module. Selectors are functions that control the job execution method
based on the input parameters. They are covered in the
:ref:`advanced-usage-selectors` topic in the advanced usage topic.

The :file:`wsgi.py` module contains a WSGI-compatible application as
specified by PEP-3333_ providing web access to the services. The
module is loaded by a WSGI middleware when the server process is
started. You may instruct your WSGI server to load this module
directly instead of starting the server through the :program:`slivka`
command.

.. _PEP-3333: https://www.python.org/dev/peps/pep-3333/

The :file:`manage.py` is an executable script which used to be the
primary way to launch slivka. Its functionality was fully replaced by
the :program:`slivka` command.

The :file:`static` directory contains static files used by the HTTP
server to render API documentation. The `OpenAPI 3.0.3`_
specification is loaded from the :file:`openapi.yaml` file and
rendered by the Redoc_ documentation generator in the
:file:`redoc-index.html`. You can view the generated documentation by
visiting the `/api/`_ endpoint on your server. You may edit those
files according to your needs or delete them altogether. If deleted,
the server will use the default files from the slivka package
resources. This feature is experimental and is subject to change in
future versions.

.. _`OpenAPI 3.0.3`: https://swagger.io/specification/
.. _Redoc: https://github.com/Redocly/redoc
.. _/api/: http://127.0.0.1:4040/api/

.. versionadded:: 0.8.0b20
   API documentation files

===============
Example Service
===============

Services are added to slivka by creating a
:file:`{service_id}.service.yaml` file inside of the :file:`services`
directory, where *service_id* is a unique identifier of the service.
When you created the new project it came with an example service
demonstrating how the service files are structured and providing a
template for adding more services.

The example service runs the :file:`scripts/example.py` command line
program located in the project directory. In fact, slivka can run
any program installed on your computer which doesn't have to be
located under the project directory.

The example script is executed with a Python interpreter and
demonstrates the usage of different kinds of command-line arguments.

.. code:: sh

  python example.py [--infile FILE] [--opt TEXT] [--rep REP[,REP,...]] \
    [--delay SECONDS] [--letter LETTER] [--flag] -- ARG

The script takes, in that order, an optional input file parameter, a
text parameter, a parameter that takes multiple comma-separated
values, a number, a value from the list of available choices, a
boolean flag and a positional argument.

The :file:`services/example.service.yaml` contains instructions on how
to turn this command line program into a web service. We will now go
through the file explaining each parameter.
The configuration files use YAML_ syntax. Make sure you are
familiar with that data format before continuing.

.. _YAML: https://yaml.org/

--------
Metadata
--------

The first few lines of the file are a good spot to place a few comments
describing the service and adding guidelines for anyone maintaining
it. All lines starting with ``#`` are ignored by the program and
serve as comments. The example already contains a few of them in
several places.

The uppermost set of properties makes service metadata. They serve an
informational purpose for the service users. The properties include
*slivka-version* for detecting compatibility between service and
library versions followed by a *name* and a *description* storing a
display name and a description of the service. Optionally, you may
include a tool's *author*, software *version*, *license* and a list of
*classifiers* helping users and client software categorise and
recognise the service.

----------------
Input Parameters
----------------

The following property, named *parameters*, typically makes the most
of the configuration file. It lists all input parameters of the
service which will be later mapped to the command line arguments.

Each key of the *parameters* mapping is a unique parameter id. It
can only contain letters, digits, dashes and underscores. The ids are
mainly used by applications to identify the parameters.
The object under each key describes the parameter. It contains
relevant information about the parameter such as its name, description,
type and value constraints.

Each parameter must include two required properties: *name* and
*type*. The *name* is the name of the service displayed to the users.
It may differ from the identifier and doesn't impose any character
restrictions. Keep it concise and self-explanatory about what the
parameter is controlling. If you need to disclose more information,
you can include it in an optional *description* property. The *type*
property defines the type of the input parameter. There are several
built-in types which should cover the majority of use cases. Those
are ``integer``, ``decimal``, ``text``, ``flag``, ``choice`` and
``file``. Additionally, the type name can be followed by a pair of
square brackets in order to change it to an array type accepting
multiple values e.g. ``text[]``.

You may specify a default value for a parameter by setting a *default*
property. The default value will be used if the parameter is not
supplied by the user explicitly. Specifying the default value is
optional.

By default, every input parameter is required and slivka will report
an error if a value for a required parameter is not provided.
This behaviour may be changed by setting a *required* property to
``false`` (default is ``true``). Note that using the default value
nullifies parameter requirement automatically making it optional.

Depending on the parameter type, there are additional properties that
can be used to impose additional constraints on the value. Numeric
types allow specifying *min* and *max* values of the parameter; text
type adds *min-length* and *max-length* constraints; choice adds
allowed *choices*. An exhaustive list of parameter types and allowed
constraints is specified in the :ref:`parameters specification`
section on the :doc:`/specification` page.

-------
Command
-------

The *command* property is a required property that contains the base
command that will be used to start the command line program.
The arguments can be supplied as an array (similar to those you pass
to the ``execl`` function) or as a string, in which case slivka will
split the string into individual arguments. The former method is
preferred if your command contains special characters and you want
to make sure it's interpreted unambiguously.

You are allowed to include environment variables in the command using
either a ``$VARIABLE`` or ``${VARIABLE}`` syntax. A literal "$"
character can be obtained by escaping it with another dollar character
such as ``$$``. Both current system environment variables and the
variables defined for that service (more on customising environment
variables later) will be used to interpolate the variables in the
command. Additionally, slivka adds a special ``$SLIVKA_HOME`` variable
that contains the absolute path to the project root directory (without
a trailing slash) which can be used to construct paths that are under
the project root directory.

The example service runs the :file:`scripts/example.py` file from the
project root directory using a default :command:`python` interpreter.

.. note::

  If the program or script is not directly available from the *PATH*
  you **must** provide an absolute path to it. Failing to do so will
  result in failing jobs with a "file not found" error.

-----------------
Program Arguments
-----------------

Once we specified the base command and the input parameters, we must
instruct slivka how to translate those inputs to the command line
arguments. The *args* parameter defines the rules of translating the
input parameters to the command line arguments. For each key specified
in the *parameters*, you need to add an entry in the *args* mapping
having the same key. Each entry value is an object defining at least
an *arg* property that contains a template for the command line
argument. A ``$(value)`` placeholder in the template will be replaced
by the input value provided by the user. The arguments are inserted
into the command line in their definition order. When the value of the
parameter is missing, the entire argument is skipped. You should not
worry about special characters, quotes or spaces in the user's input.
Slivka automatically converts all values to strings and quotes and
escapes them before inserting them into the command line. Arguments
may also contain environment variables which are processed the same
way as for the `base command <command>`_.

.. warning::

  Never evaluate user input directly. Running commands such as ``bash
  -c`` is a serious security issue.

Let's take a look at the simplest case, the *opt* parameter in the
example service.

.. code:: yaml

  opt:
    arg: --opt $(value)

This instruction passes the value of the matching *opt* input
parameter to the command line program as the ``--opt TEXT`` argument.
The *arg* template is ``--opt $(value)`` and the actual value is
substituted for the ``$(value)`` placeholder. For example, if a user
provides a *"cosy bathroom"* string as an input to the *opt*
parameter, then the constructed command line arguments are ``--opt
'cosy bathroom'``.

If the input parameter has multiple values, the argument is repeated
multiple times for each value. You can alter this behaviour by adding
a *join* property containing a character that will be used to join
multiple values into one argument. In the example the ``--rep
REP[,REP,...]`` parameter takes multiple comma-separated values,
therefore the *arg* becomes ``--rep $(value)`` and a comma character
is used for the *join*. The resulting arguments will be ``--rep
valA,valB,valC``. If *join* were not provided, the argument would be
repeated for each value ``--rep valA --rep valB --rep valC``.

.. note::

  Using space to join the values does not yield multiple arguments.
  The joined string is always treated as a single argument i.e.
  ``--rep "valA valB valC"``.

The file-type parameters are converted to absolute paths prior to
being passed to the command line and, for all intents and purposes,
can be treated as any other string. Those paths typically point
outside the working directory of the process, which well-behaved
programs should handle with no issues. However, you can add a special
*symlink* argument with a link name, which tells slivka to create a
symbolic link to the original file in the process' working directory
and to use its name instead. That's particularly useful for programs that
require input files to be present in the current working directory or
have specific name requirements. If the symbolic link could not be
created, slivka tries to create a hard link and, if it fails too, it
copies the file to the target location.

A slightly different type of parameter is a flag. It typically
doesn't have a value associated with it. Instead, it can be either in
a present or an absent state. Under the hood, flags do actually have a
value of ``"true"`` literal if enabled or nothing if disabled which
results in the parameter being skipped.

Although every input parameter must be reflected in the arguments, the
opposite is not true. You may add arguments which are not defined in
the list of parameters. We recommend naming those arguments starting
with an underscore to differentiate them from "regular" arguments.
Those arguments have no way to fetch their value from the input
parameters and therefore are always omitted unless a *default*
constant value is provided explicitly in the argument definition. They
can be used to supply constants to the command line which should not
be altered by users. In the example, we specified a *_separator*
argument which inserts ``--`` between options and positional
arguments. In order to not be skipped, we gave it a constant
placeholder value "present". The ``$(value)`` placeholder can also
be used in those constant arguments and will be set to the default
value e.g.

.. code:: yaml

  _output-file:
    arg: --output=$(value)
    default: result.out

---------------------
Environment Variables
---------------------

If a program requires environment variables to work properly, you can
define them inside an *env* property. The *env* property is optional
and, if it exists, it should contain a mapping of environment variable
names to their values. Those variables will be set for every process
started for that service. You can reference system environment
variables in the variable values using the ``${VARIABLE}`` syntax.
However, you can't include other variables from this mapping to avoid
circular dependencies and ambiguity.

In the example, we stored a ``/usr/bin/env python`` command in the
``PYTHON`` variable which could be re-used in the command as
``$PYTHON``. We also redefined the ``PATH`` variable prepending the
path to a :file:`bin` directory from the project's root directory to
it.

Every process is executed in a modified environment with all system
variables except for ``PATH`` removed and all variables from the *env*
property then added. If you need a system variable to propagate to the
program, you need to set its value to itself in the *env* e.g.

.. code:: yaml

  env:
    MY_VARIABLE: ${MY_VARIABLE}

------------
Output files
------------

The last stage after running the program is collecting its output.
Slivka covers the output written to files and to the standard output
and error streams. The *outputs* property enumerates all output files
that should be presented to the front-end users. Each key in the
mapping represents a single output file or a group of files. The only
required property of the result object is a *path* containing a path
relative to the working directory of the process or a glob_ pattern
that will be used to match output files. The standard output and error
streams are automatically redirected to :file:`stdout` and
:file:`stderr` files respectively and can be referred to by those
names.

You can include additional metadata to aid users such as a
human-readable name under the *name* property or a *media-type*
(as discussed in `RFC 2045`_) to help client software recognise the
file types.

.. _RFC 2045: https://datatracker.ietf.org/doc/html/rfc2045
.. _glob: https://en.wikipedia.org/wiki/Glob_(programming)

--------------------
Execution Management
--------------------

The last bit of the service configuration is not strictly about the
command line program, but the way it is launched on a computer. Once the
command line arguments and environment variables are sorted out, the
scheduler sends it to one of the ``Runner`` implementations. The
runner takes a list of arguments and spawns a new process on the
system. Runners available for the service are listed under the
*runners* property under the top-level *execution* property.
The runners' definition is a mapping where each key is an identifier
of the runner and each value is an object defining the runner.
It needs to contain at least a *type* property defining the class
of the runner. The type can be accompanied by a *parameters* property
containing keyword arguments that will be passed to the runner's
initializer. The available parameters vary depending on the runner
class. If no selector is specified, a runner having a *"default"*
identifier is always selected.

Currently, slivka supports four execution methods: *shell*, *slivka
queue*, *univa grid engine* and *slurm*.

The simplest of them, the ``ShellRunner`` runs programs in a default
shell as child processes. It is simple and sufficient for very low
workloads and few simultaneous jobs, however, it can easily exhaust
all system resources if too many processes are running at once.
The use of the ``ShellRunner`` is highly discouraged in production
or outside small internal networks.

A *local-queue* and an accompanying ``SlivkaQueueRunner`` offer an
improved way to spawn processes. The local queue is a separate
process which maintains a queue of pending jobs and starts new child
processes only if there is an available slot, making sure that only a
limited number of subprocesses are running at the time. The local
queues can be moved to different nodes or VMs (as long as they share
the file system with the main slivka process). The
``SlivkaQueueRunner`` accepts one parameter: ``address`` locating the
socket the local queue is listening on. If not provided, the address
from the main configuration file is used.

A ``GridEngineRunner`` utilizes `Univa/Altair Grid Engine`_, a
third-party queuing system, to execute jobs. It wraps received
commands in shell scripts and sends them to the grid engine using a
:program:`qsub` command. ``GridEngineRunner`` accepts a single
``qargs`` parameter containing a list of arguments that will be
directly appended to the :program:`qsub` command. Note that slivka
always adds ``-V --cwd -o stdout -e stderr`` arguments to the command
line and they should not be overridden.

.. _`Univa/Altair Grid Engine`: https://www.altair.com/grid-engine/

A ``SlurmRunner`` uses a Slurm_ workload manager to execute jobs. It
wraps received commands in bash scripts and submits them to Slurm
using a :program:`sbatch` command. ``SlurmRunner`` accepts a single
``sbatchargs`` parameters containing a list of arguments that will be
directly appended to the :program:`sbatch` command. Slivka
automatically includes ``--output=stdout --error=stderr --parsable``
arguments which should not be overridden.

.. _Slurm: https://slurm.schedmd.com/

Selector
========

Using selectors is an advanced topic which will be covered in the
:ref:`execution management` section of the advanced usage. The
selector is a python function or a class which takes a mapping of
input parameters and command line arguments and outputs an identifier
of the runner to be used. If more than one runner is defined under the
*runners* property then the role of the selector is to choose one of
those runners based on the job inputs. It allows the allocation of
different resources depending on the size or nature of the submitted
job. If no identifier is returned then the job request is rejected. If
only one runner is used regardless of the inputs, it should be named
``"default"`` and the *selector* property may be omitted. In that
case, a default selector which always selects a default runner is
used.
