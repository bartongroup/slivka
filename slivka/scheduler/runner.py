from abc import ABC, abstractmethod
from collections import namedtuple
from typing import List

from slivka import JobStatus

Command = namedtuple("Command", "args, cwd, env")
Job = namedtuple("Job", ["id", "cwd"])


class BaseCommandRunner(ABC):
    @abstractmethod
    def start(self, commands: List[Command]) -> List[Job]:
        """ Submits multiple jobs to the queueing system.

        Method used by runners to send jobs to the external execution
        system. Implementations of this method must start the jobs
        or schedule them for execution and return a :py:class:`Job`object
        for each newly created job in the same order that the commands
        were provided. Each job id must be json-serializable and will
        be used to pull the job status or cancel the job.

        :param commands: sequence of :py:class:`Command` tuples
            consisting of arguments list, working directory and
            environment variables
        :return: sequence of :py:class:`Job` tuples, each containing
            json-serializable job id and the working directory
        :raise Exception: submission to the queue failed
        """

    @abstractmethod
    def status(self, jobs: List[Job]) -> List[JobStatus]:
        """ Checks the status of the jobs.

        Method used by scheduler to check current status of the jobs.
        Implementations should check with underlying execution system
        the current status of the job and return them in the same
        order as the jobs. The job objects are the same tuples that
        the :py:meth:`start` method returned.

        :param jobs: sequence of :py:class:`Job`s whose status is
            being requested
        :return: list of job statuses
        """

    @abstractmethod
    def cancel(self, jobs: List[Job]):
        """ Cancels the jobs.

        Method used by scheduler to cancel the job. Implementations
        should send the cancel request to the underlying execution
        system to stop the job. It should return immediately and
        not wait for the job to be stopped.

        :param jobs: sequence of :py:class:`Job`s to cancel
        """
