import logging
import os.path
import threading
import time
from configparser import ConfigParser

import jsonschema
import yaml
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

import pybioas.utils
from pybioas.db import Session, start_session
from pybioas.db.models import Request, Result, File, JobModel
from .exc import JobRetrievalError, SubmissionError
from .executors import Executor, Job


class Scheduler:

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._shutdown_event = threading.Event()
        self._tasks = set()
        self._tasks_lock = threading.Lock()
        self._set_executors()
        self._restore_jobs()
        self._poll_thread = threading.Thread(
            target=self.database_poll_loop,
            name="PollThread"
        )
        self._collector_thread = threading.Thread(
            target=self.collector_loop,
            name="PollThread"
        )

    def _set_executors(self):
        """
        Loads executors and configurations from config file.
        For each service specifies in services.ini loads its configuration
        data and constructs executor for each configuration.
        """
        parser = ConfigParser()
        parser.optionxform = lambda option: option
        with open(pybioas.settings.SERVICE_INI) as file:
            parser.read_file(file)
        self._executors = {}
        self._limits = {}
        for service in parser.sections():
            with open(parser.get(service, 'config')) as file:
                conf_data = yaml.load(file)
            jsonschema.validate(conf_data, pybioas.utils.CONF_SCHEMA)
            self._executors[service], self._limits[service] = \
                Executor.make_from_conf(conf_data)

    def _restore_jobs(self):
        """
        Loads jobs which have queued or running status from the database
        and re-creates Job objects based on the retrieved data.
        It's intended to restore running jobs in case the scheduler was
        restarted.
        """
        with start_session() as sess:
            running = (
                sess.query(JobModel).
                filter(or_(
                    JobModel.status == JobModel.STATUS_RUNNING,
                    JobModel.status == JobModel.STATUS_QUEUED
                )).
                all()
            )
        for job_model in running:  # type: JobModel
            exe = self.get_executor(job_model.service, job_model.configuration)
            job = Job(job_model.job_ref_id, job_model.working_dir, exe)
            self._tasks.add(JobWrapper(job, job_model.request_id))

    def start(self, async=False):
        """
        Starts the scheduler and it's working threads. If `async` parameter is
        set to False, it blocks until interrupt signal is received.
        After this, it shuts the server down gracefully and waits for threads to
        join.
        Asynchorous start doesn't mean that the main process wil exit and
        subprocesses will run in the background. When started asynchonously
        you should shutdown it manually from outside.
        :param async: whether the sheduler should not block
        """
        self._collector_thread.start()
        self._poll_thread.start()
        if async:
            return
        try:
            while self.is_running:
                time.sleep(3600)
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
            self.shutdown()
            self.join()

    def shutdown(self):
        """
        Sends shutdown signal and starts exit process.
        """
        self._shutdown_event.set()

    def join(self):
        """
        Blocks until scheduler stops working.
        """
        self._collector_thread.join()
        self._poll_thread.join()

    def get_executor(self, service, configuration):
        """
        Returns the executor for specified service and configuration.
        Raises KeyError is configuration or service not found.
        :param service: service to run
        :param configuration: executor configuration
        :return: executor object for given configuration
        :rtype: Executor
        """
        return self._executors[service][configuration]

    def database_poll_loop(self):
        """
        Keeps checking database for pending requests.
        Submits a new job if one is found.
        """
        self.logger.info("Scheduler starts watching database.")
        while self.is_running:
            session = Session()
            pending_requests = (
                session.query(Request).
                options(joinedload('options')).
                filter_by(pending=True).
                all()
            )
            self.logger.debug("Found %d requests", len(pending_requests))
            try:
                for request in pending_requests:
                    self.submit_job(request)
            finally:
                session.commit()
                session.close()
            self._shutdown_event.wait(5)

    def submit_job(self, request):
        """
        Starts a new job based on the data in the database for given Request.
        :param request: request database record
        :type request: Request
        """
        options = {
            option.name: option.value
            for option in request.options
        }
        with self._tasks_lock:
            limits = self._limits[request.service]()
            configuration = limits.get_conf(options)
            executor = self.get_executor(request.service, configuration)
            request.pending = False
            request.job = JobModel(
                service=request.service,
                configuration=configuration
            )
            try:
                job = executor(options)
            except SubmissionError:
                request.job.status = JobModel.STATUS_ERROR
            else:
                request.job.job_ref_id = job.id
                request.job.working_dir = job.cwd
                self._tasks.add(JobWrapper(job, request.id))

    def collector_loop(self):
        """
        Main loop which collects finished jobs from queues.
        For each finished job it starts final procedures and saves the result
        to the database.
        """
        self.logger.info("Scheduler starts collecting tasks.")
        while self.is_running:
            session = Session()
            # noinspection PyBroadException
            try:
                for job_wrapper in self._get_finished():
                    try:
                        self._complete_job(job_wrapper, session)
                    except JobRetrievalError:
                        self.logger.error("Couldn't retrieve job result.")
            except:
                self._logger.critical(
                    "Critical error occurred, scheduler shuts down.",
                    exc_info=True
                )
                self.shutdown()
            finally:
                session.commit()
                session.close()
            self._shutdown_event.wait(5)

    def _get_finished(self):
        """
        Browses all running tasks and collects those which are finished.
        :return: set of finished tasks
        :rtype: set[JobWrapper]
        """
        self.logger.debug("Collecting finished tasks")
        with self._tasks_lock:
            finished = set()
            for job_wrapper in self._tasks:
                try:
                    if job_wrapper.job.is_finished():
                        finished.add(job_wrapper)
                except JobRetrievalError:
                    self.logger.error("Couldn't retrieve job status.")
        self.logger.debug("Found %d tasks", len(finished))
        return finished

    def _complete_job(self, job_wrapper, session):
        """
        Finalize job processing removing completed jobs from the running
        tasks and updating job status and result in the database.
        If retrieving result fails, it skips the job and tries again later.
        :param job_wrapper: wrapper of currently processed job
        :param session: current database session
        :raise JobRetrievalError:
        """
        result = job_wrapper.job.result
        self._tasks.remove(job_wrapper)
        (session.query(JobModel).
            filter(JobModel.request_id == job_wrapper.request_id).
            update({"status": job_wrapper.job.cached_status}))
        res = Result(
            return_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            request_id=job_wrapper.request_id
        )
        res.output_files = [
            File(path=path, title=os.path.basename(path))
            for path in job_wrapper.job.file_results
        ]
        session.add(res)

    @property
    def logger(self):
        """
        :return: current scheduler logger
        """
        return self._logger

    @property
    def is_running(self):
        """
        :return: if the scheduler is currently running.
        :rtype: bool
        """
        return not self._shutdown_event.is_set()


class JobWrapper:
    __slots__ = ['job', 'request_id']

    def __init__(self, job, request_id):
        """
        :type job: Job
        :type request_id: int
        """
        self.job = job
        self.request_id = request_id
