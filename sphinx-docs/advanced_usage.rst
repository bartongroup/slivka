==============
Advanced Usage
==============

--------
Limiters
--------

The job of limiter is to select one of the runners based on the input data.
It can filter-out long jobs and redirect them to the dedicated
queuing system while running small jobs locally.
The value of the parameter should contain the path to the Python
:ref:`limiter class <creating-limiter-class>` which analyses the input data and
chooses the appropriate runner for that job. The path must point to the class located
in the module importable for the current python interpreter.
The format of the path follows *package[.subpackages].classname* pattern.
The directory containing Python script file must be a valid python package
meaning that the directory and all its parent directories must contain a
*__init__.py* file and should be listed in the PYTHONPATH environment variable
if not available from the current working directory.

.. _creating-limiter-class:

Creating limiter class
======================

In your project you may create one or more Python modules
containing limiter classes. Each class should contain methods for
each runner defined in the configuration file allowing to
pick one configuration based on the values
provided by the user.

The limiter class must extend ``slivka.scheduler.Limiter`` and,
for each configuration named ``<name>``, it needs to define a method with signature

.. code-block:: python

  def limit_<name>(self, values: Mapping[str, Any]) -> bool

Parameter ``values`` passed to the function contains the dictionary of unprocessed input values.
The method must return ``True`` or ``False`` depending on whether this
runner can be used with this particular set of input values.
The configurations are tested in the order of method definitions and
the first one whose limit method returns ``True`` will be used.

Additionally, you can define ``setup(self, values: Dict)`` method which will be
run before all tests. It can be used to perform long operations and prepare and
store parameters as object properties for further use in limit methods.

Example:

.. code-block:: python

  import os

  from slivka.scheduler import Limiter

  class MyLimits(Limiter):
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

First, the ``setup`` method retrieves input file path from input data , checks its size
in bytes and stores the value in the ``input_file_size`` property.
Next, the criteria for the first configuration, less than 100B
json file or less than 20B yaml file, are tested.
If they are not met, the program continues to the second configuration
which is executed if the file size does not exceed 1000B.
Otherwise, the scheduler will refuse to start the job altogether.

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
