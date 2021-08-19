***************
Getting Started
***************

========
Overview
========

Slivka is a free software which provides easy and convenient means 
for creating web services on your local computer, server or cluster.
It is written in Python and is available both as a source code or from anaconda.

The core of the system is the scheduler which manages jobs execution,
parses command line arguments and delegates tasks to runners that
start new processes. It uses mongo database to store and exchange data
with the REST server which communicates with client applications --
takes their requests and provides information about running jobs.

.. figure:: overview.svg

  Diagram of interactions between slivka system components.
  The REST server pushes new requests to the database where
  the scheduler picks them from and dispatches to the correct
  runner. The instructions how to create web services and run
  command line programs are taken from the config files.

---------
Scheduler
---------

The scheduler sits in the middle of the job processing and controls other
components.
When the scheduler is started, it creates runners (more on that later)
for each web service specified in the configuration files.
After that, it enters its main operation mode in which it constantly monitors
the database and running jobs. Whenever a new request appears in the
database, the scheduler converts job parameters such as files, flags
and other input provided by the user into command line arguments.
They are then passed to the runner for execution and the scheduler
starts watching the job execution and writes its current status
back to the database.

-----------
REST server
-----------

REST server complements the scheduler providing a web interface
which users and client applications can use to submit new jobs
to the system.
On startup, it creates a form for each service specified in the
configuration file. The form contains the list of parameters
which the user is expected to provide to start the job.
Each parameter comes with label, description, type and
optional constraints telling the user what values are allowed.
When the job request with input parameters is received from the
client, the values are validated and, if correct, saved to
the database for the scheduler to pick them up.
As the job is running, the server also provides job status monitoring
and retrieving output files.

-------
Runners
-------

While talking about the scheduler, we mentioned that it passes jobs to
the runners for execution. Runners are internal parts of the slivka system
(custom Runners can be created though) providing an interface
between the scheduler and the software available on the operating system.
Each runner provides code that can start command line programs
and monitor their execution state. If you are an advanced user,
this allows you to write plug-ins that run your programs in new ways.

------------
Config files
------------

Configuration files contain parameters controlling the behaviour of slivka
and also serve as description of services (programs) that can be run with it.
The configuration files are situated outside of the slivka package to
guarantee portability and better isolation from the slivka internals.
As a system administrator, you are responsible for creating and maintaining
those configuration files, so the rest of this tutorial will be mostly
dedicated to them.

============
Installation
============

Slivka is provided as a source code and as an Anaconda package. Using
conda is strongly recommended, but it can also be installed with pip
or setuptools once the source code is obtained. Make sure that the
programs you intend to run are accessible from where the slivka is
installed (machine or VM). They don't have to be in the same virtual
python/conda environment though.

Installation requires Python 3.5+ (version 3.7 recommended).
Additional requirements will be downloaded and installed
automatically during slivka installation.


---------------------
Installing with conda
---------------------

Conda installation is recommended due to its simplicity. If you want
to use a dedicated virtual environment create it and install slivka
into it with the following commands:

.. code::

  conda create -n <env> python=3.7
  conda install -n <env> -c slivka -c conda-forge slivka
  conda activate <env>

substituting the environment name (e.g. slivka) for ``<env>``.
More information on how to use conda can be found in
`conda documentation`_.

.. _`conda documentation`: https://conda.io/en/latest/

-----------------------
Installing from sources
-----------------------

If you are a developer wanting to tweak slivka code to own needs
or you simply don't want to depend on conda then installation from
sources is the way to go.

Either clone the git repository ``https://github.com/bartongroup/slivka.git``
or download and extract the zip archive available here__. We suggest using
a more up-to-date development branch until the first stable version
is released.

__ https://github.com/bartongroup/slivka/archive/dev.zip

Navigate to the package directory (the one containing *setup.py*) and run ::

  python setup.py install

You can also use a shortcut command which automatically installs slivka
from the git repository with pip ::

  pip install git+git://github.com/bartongroup/slivka.git@dev

--------------
Mongo database
--------------

Slivka makes use of a `mongo database`_ to store data and exchange
messages between its components which is crucial for its operation.
If you do not have mongodb running on your system you can install it
locally in your conda environment or ask your system administrator
to install it system-wide.

.. _`mongo database`: https://www.mongodb.com


==============
Running slivka
==============

--------------------
Creating new project
--------------------

A slivka project is a collection of files (configuration files,
scripts, binaries) that, together, can be interpreted by slivka
to run a collection of programs as web services.
One slivka installation can be used to create and run multiple
projects independently, as long as they are in separate directories.

During the installation, a ``slivka`` executable was created and added to
the path. It is the main entry point which can be used to initialize
new projects and run the existing ones.

Let us start with creating an empty project. To do this, run ::

   slivka init <name>

replacing ``<name>`` with the name of the directory where the configuration
files will be stored in.
Use ``.`` if you wish to set-up the project in the current directory.

.. note::

  If the executable is not accessible from the PATH it can also be
  run as a python module ::

     python -m slivka [args...]

The newly created directory will contain default configuration files and
an example service. In the following sections we will walk through the
process of creating and configuring new services.

-----------
Starting up
-----------

At this point you are ready to launch a newly created slivka project
which already contains a dummy example service.
Navigate to the project directory and start those three processes
(make sure the mongo database is available first) ::

  slivka start server &
  slivka start scheduler &
  slivka start local-queue &

It launches a HTTP server, a scheduler and a simple worker queue locally
(``&`` runs them in background, use ``fg`` command to bring them back).

.. note::

  If your mongo database is listening on port other than the default
  or any of the ports used by slivka is already in use you can
  change them in the *config.yaml* file.

--------------
Submitting job
--------------

In this subsection we will take a look at the data exchanged in
the  client-server communication and submit
our first job using a terminal. This knowledge is not crucial to manage
and use slivka services, so feel free to skip to the next section
if it gets too technical.

In the following examples we use curl, a command line tool for transferring
data over network protocols, to send and receive data from the server.
More information can be found on the `cURL website`_.

.. _`cURL website`: https://curl.se/

Once the slivka server is up, you can send a GET request (or open the
url in the web browser) to `<http://127.0.0.1:4040/api/services>`_
in order to list currently available services.

.. code:: sh

  curl http://127.0.0.1:4040/api/services

The response will show a JSON formatted list of services, or one
"Example Service" to be more specific. Information about this one
service can also be requested from `/api/services/example`_.
The response contains the information
about the service including the list of input parameters
for that service. Each parameter needs to have a value supplied when
the new job is submitted. Seeing all those parameters and their
properties may be a bit daunting, so we focus on and break
down the last one for now.

.. code:: json

  {
    "array": false,
    "default": null,
    "description": "Required command line argument",
    "id": "arg",
    "name": "Text argument",
    "required": true,
    "type": "text"
  }

The most important property is parameter's *id*. It is used to
reference the parameter, especially when providing a value for it.
Second most important property is parameter *type* which dictates
what values will be accepted (text, number, file, etc). *Array* tells
us whether this parameter takes multiple values which is false in this
case, and *required* tells whether the value must be provided for the
new job to be started as some parameters may be optional.
*Default* indicates what value will be used if no other value is supplied.
Finally, *name* and *description* contain human-friendly name of
the parameter accompanied by a longer commentary.

In order to create a new job, we send a POST request to the
`/api/services/example/jobs`_ endpoint providing values for the
parameters in the request body using either urlencoded or multipart form.


.. _/api/services/example: http://127.0.0.1:4040/api/services/example
.. _/api/services/example/jobs: http://127.0.0.1:4040/api/services/example/jobs

.. code:: sh

  curl -d"rep=v1&rep=v2&arg=val3" http://localhost:4040/api/services/example/jobs

If you followed these instructions, then you've just submitted your
first job to slivka.
If everything went correctly, the server response should contain
the id of the new job along with other data such as its status,
submission time and parameters used.

You can follow the url specified in the *@url* property to view the
job resource along with the current progress status.

====================
Configuring services
====================

In this section we will take a closer look into the configuration
file of the example service and learn how to create our own services.

First, navigate to the *services* folder in your slivka project directory.
There is a single *example.service.yaml* file there which contains the
service configuration. Any file in this directory, whose name
ends with *service.yaml*, is automatically recognised as a service
definition. The identifier of the service is taken from the file name.
In the following sections we will go through each part of the file
one by one.

The configuration files are written in yaml_, so make sure you are
familiar with the yaml syntax before continuing.

.. _yaml: https://yaml.org/

----------------
Service metadata
----------------

Before we start, note that the lines starting with ``#`` are ignored
by the program, so they can be used for making comments.
The first few lines is a good place to write a few notes
briefly describing the service including information for
anyone who is going to maintain those files in the future.

The topmost properties contain service metadata. They serve
an informative purpose for the users of the service.
Starting from the top we have *slivka-version* which tells the slivka
version this service was written for and compatible with.
Then, *name* and *description* contain a brief service name
(not to be confused with an identifier) and a description with more
detailed information respectively. After that, you can optionally add an
*author*, *version* of the software, software *license*, and
*classifiers* which is a list of tags that may help users or software
categorise and recognise the service.

----------
Parameters
----------

The *parameters* property usually makes the biggest part of the configuration file.
This is the place where the input parameters for the service are listed
which are further mapped to the command line arguments.
If you followed the job submission guide, you may recognise those
parameters are the same that are presented to the front-end user.

Each key in the *parameters* mapping is a unique parameter id;
it can only contain letters, digits, dashes and underscores.
The object under each key defines the parameter. in order to get
you started, we are going to explain how to add/remove and define
service parameters based on the example service . The more detailed technical
information can be found in the :ref:`parameters specification<parameters specification>`.

First of all, each parameter must have a *name* and a *type* specified.
The name differs from the identifier (key) in that it doesn't have any
character restrictions and is for the human use only. Keep it concise and
self explanatory, so users know what that parameter is controlling.
If you need to disclose more information and details, you can add it
in a *description* which can contain longer text.

The parameter *type*, as the name suggests, tells users what kind
of value is expected. There are several built-in types which should
cover the majority of what command line programs need; these are:
``integer``, ``decimal``, ``text``, ``flag``, ``choice`` and ``file``.
You can immediately follow the type with a pair of square brackets to
convert it into an array so that multiple values can be provided for
that single parameter e.g. ``text[]``.

Two properties which are frequently used, but are not required,
include: *default* that specify the value which will be used if it
is not supplied by the user (skip it if you don't want to use
a default value) and *required* which allows to set whether
the value for that parameter must be provided for the job to be started
(default is ``true``). Note that settings a default value makes the
parameter automatically optional.

There are also additional properties which depend on the parameter type.
The notable ones are *min* and *max* value that can be specified for
numeric types, the *min-length* and *max-length* applicable to
texts and *choices* which must be listed for a choice type.
*Choices* require a bit of explanation since it doesn't contain
a list of choices, as would be expected, but a mapping. The keys of the
mapping is what is presented to the user, but the values are later used
in the command. This way you can hide the actual
command-line parameters and provide meaningful names for them.

-------
Command
-------

The *command* property contains the command that will be used to start
the program on the computer. It can either be a text as you would type
it into the shell or an array of arguments (similar to what you
pass to ``execl`` function). The latter might be particularly useful
if your command contains special characters and you want to be
sure it'll be split into arguments correctly.

Environment variables can be inserted using either ``$VARIABLE``
or ``${VARIABLE}`` syntax. A literal "$" character can be obtained
by escaping it with another dollar character like this: ``$$``.
Both, current environment variables and those defined in this file
(more on customising process' environment later) can be used.
Also, a special ``SLIVKA_HOME`` variable pointing to the project
directory can be used here as well.

In the example we run python binary to which we provide an *example.py*
located in the *scripts* folder under the project directory.

.. warning::

  If your program or script is not directly available from the
  *PATH* you **must** give an absolute path to it. Failing to do so
  will result in all jobs failing with "file not found" error.
  This is where ``SLIVKA_HOME`` comes in handy as it contains an
  absolute path to the project root directory.

---------
Arguments
---------

Once we have service parameters and command specified, we need to
tell slivka how to translate each parameter value to the command line
argument. Before we dive into details, we need to take a look at the
python script that will be executed. It is a dummy program, that
takes several parameters as command line arguments and produces some
text. Its usage can be summarised as follows

.. code:: sh

  example.py [--infile FILE] [--opt TEXT] [--rep REP[,REP,...]] \
    [--delay SECONDS] [--letter LETTER] [--flag] -- ARG

Here, optional parts are enclosed in brackets. As we can see, the
script takes a few optional arguments (one of which takes multiple,
comma-separated values) followed by a double dash and
a single required argument.

As you might have already noticed, those arguments match the
parameters and arguments specified in the service definition file.
For each argument in the command, we have an entry in the *args*
mapping. The entry value is an object which must at least have
*arg* property that contains a template for the command line argument.
For each of those entries, slivka tries to find a parameter with
a matching id and, if found, it replaces a user-provided value for the
``$(value)`` placeholder.

We'll now explain all the arguments in the service file one-by-one.
Let us skip the first entry for now and move on to the *opt* item.
It is a simple optional text parameter
passed to the command as ``--opt $(value)``. When users submit new jobs,
whatever value they provide as *opt* will be inserted in place of
the placeholder. You should not worry about special characters and
spaces as slivka will automatically quote and escape any of them.
It is also possible to use environment variables here. The rules for
using environment variables are the same as for `command`_.

Next one is *rep*, similar to the *opt* parameter, this one is a
text parameter, however, it can take multiple values as well.
In addition to *arg* it also has *join* property which tells what
character should be used to join multiple values into one argument.
As a result, the output will be ``--rep valA,valB,valC```.
If *join* is not specified, then the whole argument is repeated
multiple times. This would result in ``--rep valA --rep valB --rep valC``.

The *delay* parameter is a numeric type, but since all values are
converted to strings implicitly it doesn't require any special treatment.

The *letter* parameter behaves similar to a plain text parameter,
however, it's important to remember that values are converted
according to the *choices* mapping in the parameter definition prior
to being passed to the command line.

Moving on, *flag* (flag/boolean type) is a bit unusual as it doesn't
use a value and instead operates in the present/absent fashion.
Under the hood, flags do actually have a value which is either ``"true"``
string literal if enabled or no value if disabled which results in
the parameter being skipped.

After the list of optional parameters we need to place ``--`` before
the final argument. In order to place a constant in the command line
we can specify it like any other argument. Since it does not have
a corresponding input parameter, we need to specify a dummy default
value or the argument will be skipped due to the missing value.
For distinction, you can give it an id starting with an underscore.

The last parameter is passed to the command as is, without additional
prefixes, hence the value of *arg* contains ``$(value)`` only.

Last but not least, we explain the *input-file* argument. The file-type
parameters are converted to filesystem paths prior to being passed
to the command line and, for all intends and purposes, can be treated
as any other string.
Those paths are absolute and are not pointing to the
working directory where the program is run, which well-behaved
programs should have no problems with. However, in case the program you use
requires the input file to be present in it's working directory, the
solution is to add a *symlink* property to the argument definition.
This will make slivka create a symbolic link to the file inside the
program's working directory and insert
a relative path to the symlink in place of the original value.

The last thing to mention is that slivka constructs the command line
arguments in the same order as they appear in the *args* which does
not need to be the same order as in the *parameters*.
Also, any argument whose value is missing or is null is dropped from
the command.

---------------------
Environment variables
---------------------

If your program requires special environment variables to be set, or
you want to create a convenient alias for a value you can do it
in the *env* property. It contains a mapping of environment variable
names to their values that will be set when starting the command.
You can use system environment variables here as well (you can't make
references to other variables defined here though).

In our example, we have an alias for ``/usr/bin/env python`` stored
in ``PYTHON`` variable. We could have then used the aliased line
in the command by simply typing ``$PYTHON``.
We also re-define ``PATH`` to contain the *bin* folder from the
project directory followed by the original value of ``PATH``.

Slivka runs every command in a modified environment with all system
variables except ``PATH`` removed. If you need any variable
to be visible, you need to re-define it in *env*. e.g.

.. code:: yaml

  env:
    VARIABLE: ${VARIABLE}

-------
Outputs
-------

The course of action following the successful (or not) execution of the
program is collecting the results it produced. They usually come in
the form of the output files and/or the text written to the output
and error streams.

The *outputs* property enumerates all output files that will be
presented to the users. Each key represents an id of the result
which may be one, or a collection of files. The only required
property of the result object is *path* containing a relative path
or a glob_ pattern that will be used to identify the file.
The standard output and error streams are written to *stdout* and
*stderr* files respectively and can be referred to as such.

Additionally, you can provide additional metadata such as a
human-readable *name* or *media-type* (as discussed in `RFC 2045`_)
to help software recognise the content they are dealing with.

.. _RFC 2045: https://datatracker.ietf.org/doc/html/rfc2045
.. _glob: https://en.wikipedia.org/wiki/Glob_(programming)

-----------------
Execution manager
-----------------

Once the program's inputs and output are all worked out, it's finally
time to instruct slivka how to run the program. If your programs
doesn't put heavy loads on the machine and you have tiny user base,
you might get away with running them in a current shell. But, you
risk using up all the resources really quick if more using start
running more intensive programs. This is where runners comes into play.

Runners overview
================

The runner is a simple Python snippet that can take your carefully
prepared command and execute it in whatever way it was written to
do it. Currently, slivka has three built-in runners: ``ShellRunner``,
``SlivkaQueueRunner`` and ``GridEngineRunner``. This list will definitely
expand in the future as slivka will grow.

Starting with the simplest one, ``ShellRunner`` just spawns each job
as a new process in the current shell, nothing more. It's sufficient
if you are dealing with very low number of jobs as it doesn't require
any prior setup to work. Although, since there is no control
or limit on the number of simultaneous processes, it can easily
clog your system if one user decides to start hundred jobs at once.

A next improvement step is ``SlivkaQueueRunner``. It sends the jobs
to the separate process (that must be started first with
``slivka start local-queue``) that in turn runs them in the shell.
It may look just like running jobs in the current shell with extra step
in between but this step actually gives some advantages. First of all,
the queue may run on a different node or machine, so if the jobs start
to take too many resources, they won't clog the rest of the system.
Also, slivka queue keeps track of the number of running processes
and puts new job in the queue if their number exceeds a set limit.
It's far from being the proper system resources management system,
but it's intended to be lightweight and simple.

The last one, ``GridEngineRunner`` utilizes a third-party queuing
system to manage job execution. It dispatches received jobs to
the Grid Engine using ``qsub`` command and lets it do all the
resource management. You can tweak the execution parameters by
adding additional parameters that will be passed to ``qsub``.
This is certainly most advanced solution suitable
for very large systems that have Grid Engine set up.

Specifying runners
==================

Runners available for the service are listed under *runners* inside
the *execution* property. Under each key, which is runner id,
you need to specify runner *type* from one of the available types.
You can additionally provide additional *parameters* depending on the
runner. We won't go into details here as they are available in the
:ref:`execution management` section.

Selector
========

The last bit that remains to be explained is the *selector*.
In some cases you may need to have a fine grained control over
which runner is used depending on job parameters. One of the examples
is allocating different amount of memory depending on the data size.
If there is more than one runner defined then the python function
which the *selector* path is pointing to is called with command
line parameters as an argument. The function then needs to return
an identifier of the runner that will be used to run the command.
This is an advanced functionality which is beyond the introductory
tutorial, but it's noteworthy. If you want to use one runner only
name it ``"default"`` and remove *selector* line from the file.

------------------
Build your service
------------------

This is all for the basic tutorial. At this point you should
be able to modify and create simple web services with slivka.
Let us finish it with an exercise.
Try creating a *greeter* service which takes a name
from the user with a single input parameter and uses ``echo``
command to output "Hello <name>. Have a nice day." to the standard
output stream.

After that, start slivka and try submitting the job to your service and
retrieve the result.


