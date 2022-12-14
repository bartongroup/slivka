==============
Advanced Usage
==============

This page describes advanced features of slivka which involve extending
its current functionality. Most of those features require you to
write Python scripts or classes, therefore
a good knowledge of Python programming (or programming in general)
is recommended.

.. _advanced-usage-conditions:

--------------------
Parameter conditions
--------------------

As we mentioned in the :ref:`parameters specification` section, you
can provide a logical expression in the *condition* property to impose
constraints on the value that depend on other parameters. This feature
is currently experimental and must be used with care as invalid
expressions may not be properly detected and cause runtime errors.
Additionally, expressions involving array elements or files are not
supported and can result in errors when evaluated.

The conditional expressions are evaluated after the basic validation
of the input values passes successfully. If the expression evaluates
to *false*, its value is assumed to be invalid, unless the default
value was used. In such case the value is changed to *null* and the
validation is run again raising validation error if the expression
still yields *false*.

A valid expression consists of a constant value, an identifier
or an operator acting on other expressions e.g.

- ``my_param`` - a single identifier,
- ``1`` - a constant,
- ``my_param < 5`` - an operator joining two expressions into a compound
  expression.
- ``param1 > 4 and (param2 == "sometext" or param3)`` - a more complex
  expression.

Here is the list of allowed
expressions starting with simple values followed by operators in the
precedence order (highest priority first).

:identifier:
  Identifiers are used to refer to other parameters by their ids.
  The value of the referenced parameter will be substituted in place
  of the identifier during evaluation. Referencing a file type is not
  supported and results in an unexpected behaviour.
  Referencing an array type will substitute the entire array
  not its values and only a length operator (``#``) can be used on it.

:null:
  ``null`` keyword is equal to an empty value.
  It can only be used with equality and logical operators and
  it's logical value is ``false``.

:number:
  An integer or a floating point number optionally preceded by a minus
  sign. Engineering notation is also supported. A valid number has to
  start with a digit or a minus sign immediately followed by a digit.
  They can be used with equality, inequality and logical operators with
  0 being equal to ``false`` and any other value equal to ``true``.

  Examples: ``15``, ``0.21``, ``-4.41``, ``2e-4``, ``-8.22E19``.

  Invalid: ``e5``, ``.5``.

:text:
  String literals can be defined by specifying text inside double quotes
  (``"``). If the text needs to include double quote or backslash character
  they need to be escaped with a backslash character.
  Text can be used with equality, inequality (alphabetical order test)
  and ``+`` (concatenation) operators.

  Examples: ``"slivka"``, ``"\"quoted\" text"``, ``"3.14"``, ``"\\"``.

  Invalid: ``""quoted" text"``, ``"\"``, ``"\text"``.

:parentheses:
  ``(<expr>)`` Groups expressions together to force their evaluation
  before other operations.

:unary minus:
  ``- <expr>`` Must be followed by a number expression and
  returns it's negative value.

:logical not:
  ``not <expr>`` Evaluates and converts the expression following it
  to a truth value and returns its opposite.

:length:
  ``# <expr>`` Must be followed by a string or an array expression and
  returns its length as an integer.

:multiplication:
  ``<expr> * <expr>`` Performs multiplication of two numbers.

:division:
  ``<expr> / <expr>`` Performs division of two numbers.

:addition:
  ``<expr> + <expr>`` Performs addition of two numbers or
  concatenation of two strings.

:subtraction:
  ``<expr> - <expr>`` Performs subtraction of two numbers.

:inequality:
  ``<expr> < <expr>``, ``<expr> > <expr>``, ``<expr> <= <expr>`` or
  ``<expr> <= <expr>``. Tests two numbers for inequality and returns
  a truth value. Comparing two strings tests them for alphabetical
  order.

:equality:
  ``<expr> == <expr>`` or ``<expr> != <expr>`` Tests two values for
  being equal or non-equal and returns a truth value.

:logical and:
  ``<expr> and <expr>`` Performs logical *and* of two expressions converting
  them to truth values first.

:logical xor:
  ``<expr> xor <expr>`` Performs logical *xor* of two expressions converting
  them to truth values first.

:logical or:
  ``<expr> or <expr>`` Performs logical *or* of two expressions converting
  them to truth values first.

.. warning:: 
  No type or syntax checks are performed on the expressions. Any
  syntax and value errors may cause uncaught exceptions in the
  application.

.. _advanced-usage-selectors:

---------
Selectors
---------

Selector is a Python function which chooses a runner based on the
command parameters. As a quick recap of :ref:`execution management`,
each service has one or more runners which are responsible for
starting and watching jobs running on the system. If there is more
than one runner available, a selector function is used to choose the
most appropriate one for the job. It allows picking runners having
different amounts of available resources depending of the size of the
job.

The selector is a Python function which takes one argument,
the mapping of input parameter names to their values, and returns
the identifier of the runner or ``None`` to reject the job.

.. py:function:: selector(input: dict[str, str | list[str]]) -> str

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

Although slivka is still expanding, currently existing runners may
not be sufficient for some use cases. Custom runners may be as simple
as a script running a program or may involve complex data exchange
between multiple machines. We made it possible to dynamically
add new runners to the application without the need to modify the
existing slivka package.
The only requirement is to create a class extending ``slivka.scheduler.Runner``
interface, implementing all of its unimplemented methods and put it in
a Python module file (preferably in an easily accessible
location such as the project directory).

The minimal set of operations that the runner must implement is
starting/submitting the job, checking its status and cancelling it.
Here is the basic template for the custom runner class

.. code-block:: python

  from slivka.scheduler.runners import Runner, Job, Command
  from slivka import JobStatus

  class MyRunner(Runner):
    def __init__(self, *args, my_parameter=None, **kwargs):
      super().__init__(*args, **kwargs)
      # initialize your runner

    def submit(self, command: Command) -> Job:
      # start the job using given command
      # return Job object

    def check_status(self, job: Job) -> JobStatus:
      # perform status check of the job
      # return appropriate status

    def cancel(self, job: Job):
      # interrupt the job


Starting from the top of the class definition we have an :py:meth:`__init__`
method where object initialization takes place. Defining own initializer
is optional but, if it is used, it has to call the superclass'
:py:meth:`~Runner.__init__`. If your runner needs to take parameters, the easiest
way is to capture all positional arguments, then define your parameters
as keyword arguments and capture the rest. Then you can
easily pass all captured parameters to :py:meth:`Runner.__init__` without
listing them individually. However, if you decide to customize the
arguments passed, you can find a signature of the initializer below.

Next on the list is the :py:meth:`submit` method, which takes a single
:py:class:`Command` argument and returns a :py:class:`Job` tuple.
:py:class:`Command` is a namedtuple having two attributes
:py:attr:`~Command.args` - the list of arguments and
:py:attr:`~Command.cwd` - the working directory, in that order.
The ``args`` list already contains the base command and its arguments with
all values inserted, therefore no additional
processing is needed before running the command. The ``cwd`` is
an absolute path to the designated directory where process should be
started. It's the responsibility of the runner to start sub-processes
in the correct directory as they are different to the current working directory.
The directory should have been created already when the method
is called. Additionally, the :py:class:`Runner` object itself exposes
a :py:attr:`~Runner.env` attribute (accessible through ``self.env``)
containing a read-only dictionary of environment variables.
Those variables should be used in favour
of the system environment variables for job processes.

.. py:class:: Command

  Represents the command to be started by the runner. Provided to the
  :py:meth:`submit` method by the scheduler.

  .. py:attribute:: args
    :type: list[str]

    List of command line arguments. The arguments include the base
    command as well the arguments.

  .. py:attribute:: cwd
    :type: str

    Working directory where the process should be started.

The return value of the method is a :py:class:`Job`
namedtuple having two fields :py:attr:`~Job.id` - a job identifier,
and :py:attr:`~Job.cwd` - a working directory.
The identifier must be json-serializable, preferably a string or
an integer which allows the runner to uniquely identify the job
that has just been started. Working directory is, again, a directory
where the process is running. It should be the same value that
was passed to the function in the command parameter. The returned
job object is the same that will later be used in :py:meth:`check_status`
and :py:meth:`cancel` methods.

.. py:class:: Job

  Represents a running job containing the identifier and working directory.
  Object returned by :py:meth:`submit` method and later used as an
  argument to :py:meth:`check_status` and :py:meth:`cancel`.

  .. py:attribute:: id
    :type: Any

    Job id that allows its runner identify the job.
    Must be JSON serializable.

  .. py:attribute:: cwd
    :type: str

    Path to the working directory of the job.


The :py:meth:`check_status` method takes one argument, the job returned
earlier by the :py:meth:`submit` method, and returns the current status of
the job. The status must be one of the :py:class:`slivka.JobStatus` enum values.

.. py:class:: slivka.JobStatus

  .. py:attribute:: PENDING

    Job request awaits processing. Used internally by slivka.

  .. py:attribute:: REJECTED

    Job request was rejected. Used internally by slivka.

  .. py:attribute:: ACCEPTED

    Job request was accepted fur submission. Used internally by slivka.

  .. py:attribute:: QUEUED

    Job has beed submitted for execution but not started by the
    underlying queuing system (if any) yet.

  .. py:attribute:: RUNNING

    Process has been started and is currently running.

  .. py:attribute:: COMPLETED

    Job finished successfully and the results are ready.

  .. py:attribute:: CANCELLING

    Cancel request was issues and job is in process of being stopped.

  .. py:attribute:: INTERRUPTED

    Job was interrupted during it's execution by the user and is not running.

  .. py:attribute:: DELETED

    Job has been deleted from the queuing system.

  .. py:attribute:: FAILED

    Job execution failed due to invalid input or errors during the execution.

  .. py:attribute:: ERROR

    Job execution failed due to misconfigured or faulty queuing system.

  .. py:attribute:: UNKNOWN

    Job status cannot be determined.

Finally, the :py:meth:`cancel` method takes the job and is responsible
for cancelling it. It should only send a cancel request to the underlying
execution system and not wait for the job to be actually stopped.

If any irrecoverable error occurs during job submission, status check
or cancellation, caused by the Runner or its underlying execution
system malfunction, the methods should raise an exception. This will
put jobs being processed in an error state and indicate a problem with the runner.
The exception should not be raised for jobs that run properly but
did not complete successfully due to invalid input.

Additionally, each of those methods has a batch counterpart,
:py:meth:`~Runner.batch_submit`, :py:meth:`~Runner.batch_check_status`,
:py:meth:`~Runner.batch_cancel` respectively. They are supposed to
provide performance benefit by performing an action on multiple jobs
at once. Each of those methods takes a list of the objects as a single
argument and returns a list. The objects in the list have the same meaning
and types as in the single-job methods. Default implementations
call their single-job variants multiple times.

.. py:class:: Runner

  .. py:method:: __init__(self, runner_id, command, args, outputs, env)

    :param runner_id: pair of service and runner ids
    :type runner_id: RunnerID
    :param command: command passed as a shell command or a list of arguments
    :type command: str | List[str]
    :param args: argument definitions
    :type args: List[Argument]
    :param outputs: output file definitions
    :type outputs: List[OutputFile]
    :param env: custom environment variables for this service
    :type env: Map[str, str]

  .. py:attribute:: id

    Full runner identifier which is a tuple of service id and runner id.

  .. py:attribute:: command

    Base command converted to the list of arguments. The base command
    is already included in the command line parameters passed to the
    :py:meth:`.submit` method.

  .. py:attribute:: arguments

    List of arguments definitions. Those are used internally to construct
    the command line arguments passed to the :py:meth:`.submit`
    method.

  .. py:attribute:: outputs

    Output files definitions. Used internally to search the directory
    for the results.

  .. py:attribute:: env

    Environment variables defined for this service that should be
    used for new jobs. This dictionary should not be modified outside
    of the :py:meth:`.__init__` method.

  .. py:method:: start(inputs, cwd)

    Used internally by the scheduler to start a new job. Performs all preparations
    needed for the new job and calls :py:meth:`.submit`.

  .. py:method:: batch_start(inputs, cwds)

    Used internally by the scheduler to start a batch of jobs. Performs all
    preparations needed for the new jobs and calls :py:meth:`.batch_submit`

  .. py:method:: submit(command)
    :abstractmethod:

    Submits the command to the underlying execution system and returns
    the job wrapper. If an error resulting from the system malfunction
    prevents job from being properly started, an appropriate exception
    should be raised.

    :param command: A command containing arguments and working directory.
    :type command: :py:class:`Command`
    :return: A wrapper object containing job id and working directory
    :rtype: Job

  .. py:method:: check_status(job)
    :abstractmethod:

    Checks and returns the current status of the job using one of the
    :py:class:`slivka.JobStatus` values. The argument
    is the same job object as returned by the :py:meth:`.submit`
    method. If the status could not be checked due to an error, an
    appropriate exception should be raised.

    :param job: Job object as returned by :py:meth:`.submit`
    :type job: Job
    :return: Current job status.
    :rtype: slivka.JobStatus

  .. py:method:: cancel(job)
    :abstractmethod:

    Cancels currently running job. Does nothing if the job is not
    running. It should only send cancel request to the underlying
    execution system without waiting until the job is actually stopped.
    After successful cancel, consecutive status checks should result in
    ``CANCELLING`` status and then ``INTERRUPTED`` or ``DELETED``
    once the job is stopped.

    :param job: Job object as returned by :py:meth:`.submit`
    :type job: Job

  .. py:method:: batch_submit(commands)

    A batch variant of the :py:meth:`.submit` method used to submit
    multiple jobs at once. Sub-classes should re-implement this method
    if there is a way to start multiple jobs at once which offers performance
    benefits. Default implementation makes multiple calls to its single-job
    counterpart.

    :param commands: List of command tuples containing arguments and working directories.
    :type commands: List[Command]
    :return: List of jobs for each provided command.
    :rtype: List[Job]

  .. py:method:: batch_check_status(jobs)

    Batch variant of the :py:meth:`.check_status` method used to check
    statuses of multiple jobs at once. Takes a list of jobs and returns
    a list of statuses in the same order. Sub-classes should re-implement
    this method if checking status in batches provides performance
    improvement. Default implementation makes multiple calls to its
    single-job counterpart.

    :param jobs: List of jobs to check the status for.
    :type jobs: List[Job]
    :return: List of statuses for each passed job.
    :rtype: List[JobStatus]

  .. py:method:: batch_cancel(jobs)

    Batch variant of the :py:meth:`.cancel` method. Takes a list of
    jobs and cancels them all.
    Sub-classes should re-implement this method if cancelling jobs
    in batches is more efficient than doing it individually.
    Default implementation makes multiple calls to its single-job
    counterpart.

    :param jobs: List of jobs to be cancelled.
    :type jobs: List[Job]
