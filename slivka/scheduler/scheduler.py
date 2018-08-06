import logging
import os
import signal
import threading
from collections import namedtuple, deque, defaultdict
from fnmatch import fnmatch

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

import slivka.utils
from slivka.db import Session, start_session
from slivka.db.models import Request, File
from slivka.scheduler.exceptions import QueueBrokenError, \
    QueueTemporarilyUnavailableError, QueueError
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
        self._running_jobs = defaultdict(set)
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
                    runner_class = (
                        self._runner_factories[request.service]
                        .get_runner_class(request.run_configuration)
                    )
                    job_handler.runner_class = runner_class
                    self._running_jobs[runner_class].add(
                        JobHandlerRequestPair(job_handler, request)
                    )
                else:
                    request.status = JobStatus.UNDEFINED
            session.commit()

    def register_terminate_signal(self, *signals):
        for sig in signals:
            signal.signal(sig, self.terminate_signal_handler)

    def terminate_signal_handler(self, _signum, _frame):
        self.logger.warning("Termination signal received.")
        self.stop()

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
                    self._shutdown_event.wait(1)
            except KeyboardInterrupt:
                self.logger.info("Keyboard Interrupt; Shutting down...")
                self.stop()
            finally:
                self.shutdown()
                self.logger.info("Finished")

    def stop(self):
        self._shutdown_event.set()

    def shutdown(self):
        """
        Sends shutdown signal and starts exit process.
        """
        if self.is_running:
            raise RuntimeError("Can't shutdown while running")
        self._shutdown_event.set()
        self.logger.debug("Shutdown event set")
        self.join()

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
            runners = []
            for request in pending_requests:
                self.logger.debug('Processing request %r', request)
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
                        self._running_jobs[runner.__class__].add(
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
            for runner_class, jobs in self._running_jobs.items():
                if not jobs:
                    continue
                disposable_jobs = set()
                handlers = [job.job_handler for job in jobs]
                try:
                    statuses = dict(runner_class.get_job_status(handlers))
                    for job in jobs:
                        handler, request = job
                        session.add(request)
                        request.status = statuses[handler]
                        skip_paths = {f.path for f in request.files}
                        request.files.extend(
                            self._collect_output_files(
                                request.service, handler.cwd, skip_paths
                            )
                        )
                        if request.is_finished():
                            self.logger.info('Job finished')
                            disposable_jobs.add(job)
                except QueueTemporarilyUnavailableError:
                    self.logger.warning('Queue not available')
                except QueueBrokenError:
                    for job in jobs:
                        job.request.status = JobStatus.UNDEFINED
                        self.logger.exception('Could not retrieve job status.')
                        disposable_jobs.add(job)
                jobs.difference_update(disposable_jobs)
        except Exception:
            self.logger.exception(
                'Critical error occurred, scheduler shuts down'
            )
            self.shutdown()
        finally:
            self._running_jobs_lock.release()
            session.commit()
            session.close()

    def _collect_output_files(self, service, cwd, skip_paths=set()):
        results = self._runner_factories[service].results
        return [
            File(path=entry.path, mimetype=result.mimetype)
            for entry in slivka.utils.recursive_scandir(cwd)
            for result in results
            if ((entry.path not in skip_paths) and
                fnmatch(os.path.relpath(entry.path, cwd), result.path))
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
