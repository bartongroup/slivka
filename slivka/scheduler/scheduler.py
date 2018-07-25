import logging
import os
import signal
import threading
import time
from collections import namedtuple, deque
from fnmatch import fnmatch

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

import slivka.utils
from slivka.db import Session, start_session
from slivka.db.models import Request, File
from slivka.scheduler.exceptions import QueueBrokenError, \
    QueueTemporarilyUnavailableError, JobNotFoundError, QueueError
from slivka.scheduler.execution_manager import RunnerFactory
from slivka.utils import JobStatus

RunnerRequestPair = namedtuple('RunnerRequestPair', ['runner', 'request'])
JobHandlerRequestPair = namedtuple('JobHandlerRequestPair',
                                   ['job_handler', 'request'])


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
        self._running_jobs = set()
        self._running_jobs_lock = threading.RLock()
        self._pending_runners = deque()

        self._runner_factories = {
            conf.service: RunnerFactory.new_from_configuration(
                conf.execution_config)
            for conf in slivka.settings.service_configurations.values()
        }
        self._restore_runners()
        self._restore_jobs()

        self._watcher_thread = threading.Thread(
            target=self._database_watcher_loop,
            name="PollThread"
        )
        self._runner_thread = threading.Thread(
            target=self._runner_observer_loop,
            name="CollectorThread"
        )

    def _restore_runners(self):
        """Restores runners that has been prepared, but not submitted."""
        with start_session() as session:
            accepted_requests = (
                session.query(Request)
                .options(joinedload('options'))
                .filter_by(status_string=JobStatus.ACCEPTED.value)
                .all()
            )
            for request in accepted_requests:
                runner = self._build_runner(request, new_cwd=False)
                if runner is None:
                    request.status = JobStatus.ERROR
                    self.logger.warning('Runner cannot be restored.')
                else:
                    self._pending_runners.append(
                        RunnerRequestPair(runner, request)
                    )
            session.commit()

    def _restore_jobs(self):
        """Recreated hob handlers from currently running requests."""
        with start_session() as session:
            running_requests = (
                session.query(Request)
                .filter(or_(Request.status_string == JobStatus.RUNNING.value,
                            Request.status_string == JobStatus.QUEUED.value))
                .all()
            )
            for request in running_requests:
                job_handler = (self._runner_factories[request.service]
                               .get_runner_class(request.run_configuration)
                               .get_job_handler_class()
                               .deserialize(request.serial_job_handler))
                if job_handler is not None:
                    job_handler.cwd = request.working_dir
                    self._running_jobs.add(
                        JobHandlerRequestPair(job_handler, request)
                    )
                else:
                    request.status = JobStatus.UNDEFINED
            session.commit()

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
        self._watcher_thread.start()
        self._runner_thread.start()
        if block:
            self.logger.info("Child threads started. Press Ctrl+C to quit")
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
        self.logger.debug("Shutdown event set")

    def join(self):
        """
        Blocks until scheduler stops working.
        """
        self._runner_thread.join()
        self._watcher_thread.join()

    def _database_watcher_loop(self):
        """
        Keeps checking database for pending requests.
        Submits a new job if one is found.
        """
        self.logger.info("Scheduler is watching database.")
        while self.is_running:
            session = Session()
            pending_requests = (
                session.query(Request)
                .options(joinedload('options'))
                .filter_by(status_string=JobStatus.PENDING.value)
                .all()
            )
            self.logger.debug("Found %d requests", len(pending_requests))
            runners = []
            for request in pending_requests:
                try:
                    runner = self._build_runner(request)
                    if runner is None:
                        raise QueueError('Runner could not be created')
                    runner.prepare()
                    request.status = JobStatus.ACCEPTED
                    runners.append(RunnerRequestPair(runner, request))
                except Exception:
                    request.status = JobStatus.ERROR
                    self.logger.exception("Setting up the runner failed.")
            session.commit()
            session.close()
            self._pending_runners.extend(runners)
            self._shutdown_event.wait(0.5)

    def _build_runner(self, request, new_cwd=True):
        values = {
            option.name: option.value
            for option in request.options
        }
        runner_factory = self._runner_factories[request.service]
        if new_cwd:
            cwd = os.path.join(slivka.settings.WORK_DIR, request.uuid)
            request.working_dir = cwd
        else:
            cwd = request.working_dir
        return runner_factory.new_runner(values, cwd)

    def _runner_observer_loop(self):
        try:
            while self.is_running:
                self._submit_runners()
                self._update_job_statuses()
        except Exception:
            self.logger.exception(
                'Critical error occurred, scheduler shuts down'
            )
            self.shutdown()

    def _submit_runners(self):
        retry_runners = []
        session = Session()
        try:
            while self._pending_runners:
                runner, request = self._pending_runners.popleft()
                session.add(request)
                try:
                    job_handler = runner.start()
                    self.logger.info('Job submitted')
                except QueueTemporarilyUnavailableError:
                    retry_runners.append(RunnerRequestPair(runner, request))
                    self.logger.info('Job submission deferred')
                except QueueError:
                    request.status = JobStatus.ERROR
                    self.logger.exception(
                        'Job cannot be scheduled due to the queue error'
                    )
                else:
                    request.status = JobStatus.QUEUED
                    request.serial_job_handler = job_handler.serialize()
                    with self._running_jobs_lock:
                        self._running_jobs.add(
                            JobHandlerRequestPair(job_handler, request)
                        )
        finally:
            session.commit()
            session.close()
            self._pending_runners.extend(retry_runners)

    def _update_job_statuses(self):
        session = Session()
        self._running_jobs_lock.acquire()
        try:
            disposable_jobs = set()
            for pair in self._running_jobs:
                job_handler = pair.job_handler
                request = pair.request
                try:
                    session.add(request)
                    request.status = job_handler.get_status()
                    if request.is_finished():
                        request.files = self._collect_output_files(
                            request.service, job_handler.cwd
                        )
                        self.logger.info('Job finished')
                        disposable_jobs.add(pair)
                except QueueTemporarilyUnavailableError:
                    self.logger.warning('Queue not available')
                except (QueueBrokenError, JobNotFoundError):
                    request.status = JobStatus.UNDEFINED
                    self.logger.exception('Could not retrieve job status.')
                    disposable_jobs.add(pair)
            self._running_jobs.difference_update(disposable_jobs)
        except Exception:
            self.logger.exception(
                'Critical error occurred, scheduler shuts down'
            )
            self.shutdown()
        finally:
            self._running_jobs_lock.release()
            session.commit()
            session.close()

    def _collect_output_files(self, service, cwd):
        results = self._runner_factories[service].results
        return [
            File(path=entry.path, mimetype=result.mimetype)
            for entry in slivka.utils.recursive_scandir(cwd)
            for result in results
            if fnmatch(os.path.relpath(entry.path, cwd), result.path)
        ]

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
