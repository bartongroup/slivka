***************
Getting Started
***************

========
Overview
========

Slivka is a free software which provides easy and convenient means
for creating web services on your local computer, server or cluster.
It is written in Python and is available as a source code or from anaconda.

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
this allows you to write plugins that run your programs in new ways.

------------
Config files
------------

Configuration files live outside of the slivka module and provide
system settings and service information. As a system
administrator, you are responsible for creating and maintaining
those configuration files, so the rest of this tutorial will be mostly
dedicated to them.

============
Installation
============

Slivka is provided as a source code and an Anaconda package. Using
conda is strongly recommended, but it can also be installed with pip
or setuptools once the source code is obtained. Make sure that the
programs you intend to run are accessible from where the slivka is
installed (machine or VM). They don't have to be in the same virtual
python/conda environment though.

Installation requires Python 3.5+ (version 3.7 recommended).
Additional requirements that will be downloaded and installed 
automatically, include:

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


---------------------
Installing with conda
---------------------

Conda installation is recommended due to its simplicity. If you want
to use a dedicated virtual environment create it and install slivka with:

.. code:: 

  conda create -n <env> python=3.7
  conda install -n <env> -c mmwarowny -c conda-forge slivka
  conda activate <env>

substituting environemnt name (e.g. slivka) for ``<env>``.
More information can be found in `conda documentation`_.

.. _`conda documentation`: https://conda.io/en/latest/

-----------------------
Installing from sources
-----------------------

If you are a developer wanting to tweak slivka code to own needs
or you simply don't want to depend on conda then installation from
sources is the way to go.

Either clone the git repository ``https://github.com/bartongroup/slivka.git``
or download and extract the zip archive available here_. We suggest using
a more up-to-date development branch until the first stable version
is released.

.. _here: https://github.com/bartongroup/slivka/archive/dev.zip

Navigate to the package directory (the one containing *setup.py*) and run ::

  python setup.py install

You can also use a shortcut command which automatically installs slivka
from the git repository with pip ::

  pip install git+git://github.com/bartongroup/slivka.git@dev

--------------
Mongo database
--------------

Slivka makes use of `mongo database`_ to store data and exchange
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

A slivka project is a single instance of slivka with its own settings
and collection of services. You can create as many instances as you want
each running in a separate directory.

During installation, a ``slivka`` executable was created and added to
your path. It can be used to initialize new projects and run slivka.

Let us start with initializing an empty project. To do this, run ::

   slivka init <name>

replacing ``<name>`` with the name of the directory where the configuration 
files will be stored in.
Use ``.`` if you wish to set-up the project in the current directory.

.. note::

  If the executable is not accessible from the PATH it can also be
  run as a python module ::

     python -m slivka [args...]

The newly created directory will contain default setting files and 
an example service. In the following sections we will walk through the 
process of creating and configuring new services.

-----------
Starting up
-----------

At this point you are ready to launch a newly created slivka project.
Navigate to the project directory and start three processes ::

  slivka start server &
  slivka start scheduler &
  slivka start local-queue &

It launches a HTTP server, a scheduler and a simple worker queue locally
(``&`` runs them in background, use ``fg`` command to bring them back).

.. note::

  If your mongo database is listening on port other than the default
  or any of the ports used by slivka is already in use you can
  change them in the *settings.yaml* file.

--------------
Submitting job
--------------

Now, you can send a GET request or navigate with your web browser to
`<http://127.0.0.1:8000/api/services>`_ to see the list of currently
available services, or one "Example Service" to be specific.

Moving on to */api/services/example* will show you the details of 
the service along with the list of form fields a.k.a. input parameters
of that service. Don't worry if the details doesn't make much sense
yet. For now, notice one field named *msg* which we are going to use.

.. code:: json

  {
    "type": "text",
    "name": "msg",
    "label": "Message",
    "description": "Message printed to the output file",
    "required": true,
    "multiple": false,
    "default": null,
    "minLength": 3,
    "maxLength": 15
  }

This tells us that one of the parameters the example service accepts
is named "msg", it is a required parameter and its length should be
between 3 and 15 characters. In order to submit a new job, send a POST
request to that endpoint providing a value for the *msg* parameter. 
Using curl:

.. code:: sh

  curl -d"msg=hello world" http://localhost:8000/api/services/example

Congratulations, you've just submitted the first job to your slivka
instance. You should have received the id of the newly created job and
slivka should have started working on it. The server response will look
like this:

.. code:: json

  {
    "statuscode": 202,
    "uuid": "<job uuid>",
    "URI": "/api/tasks/<job uuid>"
  }

You can follow the *URI* to see the current job status and get another URI
pointing to the output files.

.. code:: json

  {
    "statuscode": 200,
    "status": "COMPLETED",
    "ready": true,
    "filesURI": "/api/tasks/<job uuid>/files"
  }

====================
Configuring services
====================

Until now, we've only seen slivka using the existing example
service. In this section we will take a closer look into the configuration
file of the example service and learn how to create our own services.

First, navigate to the *services* folder in your slivka project directory.
It contains a single *example.service.yaml* file which contains the
service information. We will go through each section of the file.
The configuration files use yaml_, so please familiarize with the yaml
syntax before continuing.

.. _yaml: https://yaml.org/

----------------
Service metadata
----------------

Lines starting with ``#`` are comments. They are completely ignored by
the program and can be used as notes. First couple of lines are a good place
do place a few comments briefly describing the service and include
some information for others who, apart from you, would edit this file.

Next, comes the label of the service. This is the full name of the
service which will be displayed to users. Use meaningful names which
allow to recognise what process the service is running.

After that you can see a list of classifiers. This element is optional
and can be used to tag and categorise the services. One use case is to
provide additional information to client applications.

----
Form
----

This section usually makes the most of the configuration file. This is
the place where the input parameters for the service are defined.
Slivka uses those to construct input forms which you already saw when
going through the job submission process. Each key represents a unique
field name which serves as an identifier and is used as a parameter
name in a HTTP request. Preferably, it should contain lowercase letters
dashes and underscores only.

There are three values nested under each field: *label*, *description*
and *value*. *Label* is a full name of the field which client applications
are going to display to the users. Just like with the service labels,
field labels should be relatively short and meaningful to the users.
Next, there is a *description* parameter containing detailed help text
for the field. It should contain all the information about the parameter
such as allowed values or effects it has on the program execution.
The last parameter -- *value* -- describes constraints imposed on the
field value. Specifying the parameter type is required. Additionally,
you can set whether the field is required (default is yes) and specify
a default value used when no value is given by the user. Allowed types
and type specific parameters are discribed in the 
:ref:`value object <value-object-spec>`
specification.

-------
Command
-------

The *command* section is a complementary part to the *form*. It contains
information on how to run the command line program, connects form
parameters to the command line arguments and specify output files.
Our example service runs an *example.py* service located in the *scripts*
directory under the project directory. The command has the following syntax

.. code:: sh

  example.py --infile <input> -t <message> -r <repeat> -w <sleep> --log -v <output>

Base
====

First, the configuration file defines a *baseCommand* which is a base
executable which other arguments are appended to. In this case we want to
run the example script with current python interpreter. ::

  python ${SLIVKA_HOME}/scripts/example.py

You are free to use environment variables using stardard bash syntax.
In this case, we uses *SLIVKA_HOME* which is a variable set on slivka
startup that points to the project directory.

Inputs
======

The following part called *inputs* is, not coincidentally, similar to the form
section. It specifies how each value from the form is translated to the
command line argument. Each form field is connected to it's corresponding
field in the input parameters list which in turn corresponds to command
line parameters (see the example command above).

Our *example.py* command takes an input file ``--input <input>`` as the
first parameter. Therefore, we specify *input-file* parameter which will
take the file from the *input-file* form field. Then, we define how
the argument shall look like in the command, that is ``--input $(value)``.
Slivka uses ``$(value)`` as a placeholder for the actual value that will
be set later. Next comes the type of the argument; in this case it's
a *file*, but other possibilities are: *string* (default), *number*,
*flag* and *array*. File type allows to specify additional *symlink* parameter
which, if present, makes slivka create a symlink to the input file inside the
process' working directory and pass relative path to the symlink as
a value instead of the full path to the file. This is particularly useful
for programs that require all input files to be present in the
current working directory.

Remaining parameters follow the same syntax as the first one mapping
form fields to the consecutive parameters of the example script.
The only exception is the last parameter *_verbose* which doesn't
have matching field. It demonstrates that you can add parameters which
are not in the form but you must provide their *value* explicitly.
We suggest using names starting with an underscore for those detached
arguments.

Arguments
=========

This part contains the list of arguments which will be appended
to each command. It might be convenient in cases when the program takes
modifiable options followed by constant parameters. In many cases, however,
this part can be skipped as detached input parameters provide the same
functionality.

Environment variables
=====================

If your program requires a special set of environment variables, they
should be specified in the *env* part as a mapping of variable name to
its new value. 
You can also use current system environment variables in the value.

.. code:: yaml

  env:
    PATH: ${HOME}/bin:${PATH}

Here, we set *PATH* variable to the current *PATH* with *~/bin*
prepended.

.. warning::

  Slivka runs each program in a new environment passing only *PATH* and
  *SLIVKA_HOME* variables in addition to those provided in *env*.
  All other variables are stripped off.

Outputs
=======

Last but not least, the *outputs* part defines output files created
by the program. Each file (or group of files) is given by the name-key
under which you specify the *path* to the file (relative to the process'
working directory). Path can be a file name or a glob_ pattern.
Special names: *stdout* and *stderr* are reserved for standard output
and error streams. Additionally, you can provide a *media-type* to help
web browsers and clients recognise the file type.

.. _glob: https://en.wikipedia.org/wiki/Glob_(programming)

-------
Runners
-------

Once the program details are specified, it's  time to define runners that
will be used to execute the job. In the *runners* sections, specify
the *default* runner setting its *class* to either ``SlivkaQueueRunner``
so it will be run with the slivka worker queue, or ``GridEngineRunner``
to use ``qsub`` to start the jobs. GridEngineRunner also allows additional
parameter named *qsub_args* containing a list of arguments passed
directly to ``qsub``. Example:

.. code:: yaml

  default:
    class: GridEngineRunner
    parameters:
      qsub_args:
        - -P
        - webservices
        - -q
        - 64bit-pri.q

More detailed information regarding runner definition can be found in
the :ref:`runner <runners-spec>` specification.

------------------
Build your service
------------------

At this point you have enough information to create your own services.
As an exercise, try creating a *greeter* service which takes a name
from the user and uses ``echo`` command to output "Hello <name>.
Have a nice day." Try using as much elements as you can such as
environemnt variables, detached parameters and arguments list.

After that, start slivka and try submitting the job to your service and
retrieve the result.


