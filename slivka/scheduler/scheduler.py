import logging
import threading
import time

import jsonschema
import yaml
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

import slivka.utils
from slivka.db import Session, start_session
from slivka.db.models import Request, File, JobModel
from slivka.scheduler.exceptions import QueueBrokenError, \
    QueueUnavailableError, JobNotFoundError
from slivka.scheduler.executors import Executor, Job


class Scheduler:
    """Scans the database for new tasks and dispatches them to executors.

    A single object of this class is created when the scheduler is started from
    the command line using ``manage.py scheduler``. Having been started, it
    repeatedly polls the database for new job requests. When a pending request
    is found, it is started with an appropriate executor
    """

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._shutdown_event = threading.Event()
        self._ongoing_tasks = set()
        self._tasks_lock = threading.RLock()
        self._set_executors()
        self._restore_jobs()
        self._poll_thread = threading.Thread(
            target=self.database_poll_loop,
            name="PollThread"
        )
        self._collector_thread = threading.Thread(
            target=self.collector_loop,
            name="CollectorThread"
        )

    def _set_executors(self):
        """Load executors and configurations from the config file.

        For each service specifies in services.ini loads its configuration
        data and constructs executor for each configuration.
        """
        parser = slivka.settings.CONFIG
        self._executors = {}
        self._limits = {}
        for service in parser.sections():
            with open(parser.get(service, 'config')) as file:
                conf_data = yaml.load(file)
            jsonschema.validate(conf_data, slivka.utils.CONF_SCHEMA)
            (self._executors[service], self._limits[service]) = \
                Executor.make_from_conf(conf_data)

    def _restore_jobs(self):
        """
        Loads jobs which have queued or running status from the database
        and re-creates Job objects based on the retrieved data.
        It's restores running job handlers in case the scheduler was
        restarted.
        """
        with start_session() as session:
            running = (
                session.query(JobModel)
                .filter(or_(
                    JobModel.status == JobModel.STATUS_RUNNING,
                    JobModel.status == JobModel.STATUS_QUEUED
                ))
                .all()
            )
        for job_model in running:  # type: JobModel
            exe = self.get_executor(job_model.service, job_model.configuration)
            job = Job(job_model.job_ref_id, job_model.working_dir, exe)
            self._ongoing_tasks.add(RunningTask(job, job_model.request_id))

    def start(self, block=True):
        """Start the scheduler and it's working threads.

        It launches poller and collector threads of the scheduler which scan
        the database and dispatch the tasks respectively. If ``async``
        parameter is set to ``False``, it blocks until keyboard interrupt
        signal is received. After that, it stops the polling and collecting
        threads and join them before returning.

        Setting ``block`` to ``False`` will cause the method to return
        immediately after spawning collector and poll threads which will
        run in the background. When started asynchronously, the scheduler's
        shutdown method shoud be called manually by the main thread.
        This option is especially usefun in interactive debugging of testing.

        :param block: whether the scheduler should block
        """
        self._collector_thread.start()
        self._poll_thread.start()
        if block:
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
                session.query(Request)
                .options(joinedload('options'))
                .filter_by(pending=True)
                .all()
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
            job_model = JobModel(
                service=request.service,
                configuration=configuration
            )
            if configuration is None:
                job_model.status = JobModel.STATUS_ERROR
            else:
                executor = self.get_executor(request.service, configuration)
                try:
                    job_wrapper = executor(options)
                except QueueUnavailableError:
                    return
                except QueueBrokenError:
                    job_model.status = JobModel.STATUS_ERROR
                else:
                    job_model.status = JobModel.STATUS_QUEUED
                    job_model.job_ref_id = job_wrapper.id
                    job_model.working_dir = job_wrapper.cwd
                    job_model.files = [
                        File(path=path) for path in job_wrapper.log_paths
                    ]
                    # todo: lock should be acquired here
                    self._ongoing_tasks.add(RunningTask(job_wrapper, request.id))
        request.job = job_model
        request.pending = False

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
                finished, broken = self._collect_tasks()
                for task in finished:
                    try:
                        self._finalize_task(task, session)
                    except QueueUnavailableError:
                        self.logger.warning("Queue unavailable")
                    except (QueueBrokenError, JobNotFoundError):
                        self.logger.error("Couldn't retrieve job result.")
                        broken.add(task)
                for task in broken:
                    self._dispose_task(task, session)
            except Exception:
                self._logger.critical(
                    "Critical error occurred, scheduler shuts down.",
                    exc_info=True
                )
                self.shutdown()
            finally:
                session.commit()
                session.close()
            self._shutdown_event.wait(5)

    def _collect_tasks(self):
        """
        Browses all running tasks and collects those which are finished.

        :return: sets of finished and broken tasks
        :rtype: (set[RunningTask], set[RunningTask])
        """
        self.logger.debug("Collecting finished tasks")
        finished = set()
        broken = set()
        with self._tasks_lock:
            for task in self._ongoing_tasks:
                try:
                    if task.job.is_finished():
                        finished.add(task)
                except QueueUnavailableError:
                    self.logger.warning("Queue unavailable")
                except (QueueBrokenError, JobNotFoundError):
                    self.logger.exception("Couldn't retrieve job status.")
                    broken.add(task)
        self.logger.debug("Found %d tasks", len(finished))
        return finished, broken

    def _finalize_task(self, task, session):
        """
        Finalize job processing removing completed jobs from the running
        tasks and updating job status and result in the database.
        If retrieving result fails, it skips the job and tries again later.

        :param task: wrapper of currently processed job
        :param session: current database session
        :raise QueueBrokenError:
        :raise JobNotFoundError:
        :raise QueueUnavailableError:
        """
        self.logger.debug('Completed job %s', task.job)
        with self._tasks_lock:
            self._ongoing_tasks.remove(task)
        job_model = (session.query(JobModel)
                     .filter(JobModel.request_id == task.request_id)
                     .one())
        job_model.status = task.job.cached_status
        job_model.return_code = task.job.return_code
        session.add_all([
            File(path=path, job=job_model)
            for path in task.job.result_paths
        ])

    def _dispose_task(self, task, session):
        """
        Discards broken jobs from the scheduler and marks them as erroneous.

        :param task: wrapper of currently processed job
        :param session: current open database session
        :type session: sqlalchemy.orm.Session
        """
        with self._tasks_lock:
            self._ongoing_tasks.remove(task)
        (session.query(JobModel)
         .filter(JobModel.request_id == task.request_id)
         .update({"status": task.job.cached_status}))

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


class RunningTask:
    __slots__ = ['job', 'request_id']

    def __init__(self, job, request_id):
        """
        :type job: Job
        :type request_id: int
        """
        self.job = job
        self.request_id = request_id
