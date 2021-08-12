==============
Advanced Usage
==============

This page describes advanced features of slivka which involve extending
its current functionality. Most of those features require you to
write Python scripts or classes, therefore
a good knowledge of Python programming (or programming in general)
is required.

---------
Selectors
---------

Selector is a Python function which chooses a runner based on the
command parameters. As a quick recap of :ref:`execution management`,
each service has one or more runners which are responsible for
starting and watching jobs running on the system.
If there is more than one runner available, a selector function
is used to choose the most appropriate one for the job.
Since runners may have different configurations, it is possible
to make different amount of resources available to them and then
dispatch the jobs depending on their size and needs.

The selector is a Python function which takes one argument,
the mapping of input parameter names to their values, and returns
the identifier of the runner or ``None`` to reject the job.
The keys of the mapping consist of the ids of the input parameters
as defined in the service configuration. They are mapped to the values
provided by the user after being converted to the command
line parameters. Each value can be either of a string type or
a list of strings in case of multiple parameters.

Example:

.. code-block:: python

  def my_selector(values: Mapping) -> str:
    # set up all variables e.g. read files or do calculations
    # return runner id depending on the conditions
    if cond1:
      return "runner1"
    elif cond2:
      return "runner2"
    else:
      return None

The selector is provided in the service configuration file alongside
runners using *selector* property.
The value of the parameter should contain a Python-like path
to the function in ``package[.subpackage].function`` format.
The module containing the function must be importable from the current
interpreter.
If the file is located in a sub-directory, that directory must be a valid
Python package i.e. contain an *__init__.py* file and should be listed
in the ``PYTHONPATH`` environment variable if not directly accessible
from the project's root directory.

--------------
Custom Runners
--------------

Sometimes there is a need for a custom submission method e.g. when using a different queuing system
which is not natively supported by Slivka. Custom runner may be as simple as a script executing
a new subprocess or may involve data exchange between multiple machines.

Basic functionality
===================

A minimal runner is limited to two operations:

- start new jobs
- check job status

Every class implementing abstract runner must define two methods responsible for those two operations.

.. code-block:: python

  def submit(self, cmd: List[str], cwd: str) -> Any

The ``submit`` method is invoked once to start/submit the job to the queuing engine.
The ``cmd`` parameter is the list of command line arguments similar to those
passed to POSIX `execv function`_. The ``cwd`` parameter is an absolute path to the designated
directory where the command should be executed. The directory is already created when
the method is called. Additionally, you may access a read-only dictionary of environment variables
stored in ``self.env`` object property. New jobs should use these variables rather than
global variables accessible form ``os.environ``.
The method should return a job identifier which will be further used to monitor the job status.
The only restriction imposed on the job identifier is it must be json-serializable
i.e. it may only consist of (possibly nested) dictionaries, lists, strings, booleans, numbers and nulls.
The job id should contain all the data needed to check the job status.
If this method raises an exception, the job status is set to ``JobStatus.ERROR`` automatically.

.. _`execv function`: https://linux.die.net/man/3/execv

.. code-block:: python

  @classmethod
  def check_status(cls, job_id: Any, cwd: str) -> JobStatus

The ``check_status`` class method is invoked periodically for each running job to monitor the changes
of their status. The ``job_id`` parameter is the json-object previously returned by ``submit``
and ``cwd`` is the path to the current working directory of that job.
The method should return ``slivka.JobStatus`` corresponding to the current status of the job.
Once the value corresponding to the finished job is returned, the status of that job will not be checked anymore.
If this method raises an exception, the job status is set to ``JobStatus.ERROR`` automatically.
