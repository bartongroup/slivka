import logging
import signal
import tempfile
import threading
import time
from collections import deque, defaultdict

import slivka.utils
from slivka.db import mongo
from slivka.db.documents import JobRequest, JobMetadata
from .exceptions import (QueueBrokenError,
                         QueueTemporarilyUnavailableError,
                         QueueError)
from .execution_manager import RunnerFactory
from slivka.utils import JobStatus


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
        # self._restore_runners()
        # self._restore_jobs()

        self._watcher_thread = threading.Thread(
            target=self._database_watcher_loop,
            name="PollThread"
        )
        self._runner_thread = threading.Thread(
            target=self._runner_observer_loop,
            name="CollectorThread"
        )

    # def _restore_runners(self):
    #     """Restores runners that has been prepared, but not submitted."""
    #     with start_session() as session:
    #         accepted_requests = (
    #             session.query(Request)
    #             .options(joinedload('options'))
    #             .filter_by(status_string=JobStatus.ACCEPTED.value)
    #             .all()
    #         )
    #         for request in accepted_requests:
    #             runner = self._build_runner(request, new_cwd=False)
    #             if runner is None:
    #                 request.status = JobStatus.ERROR
    #                 self.logger.warning('Runner cannot be restored.')
    #             else:
    #                 self._pending_runners.append(
    #                     RunnerRequestPair(runner, request)
    #                 )
    #         session.commit()

    # def _restore_jobs(self):
    #     """Recreated hob handlers from currently running requests."""
    #     with start_session() as session:
    #         running_requests = (
    #             session.query(Request)
    #             .filter(or_(Request.status_string == JobStatus.RUNNING.value,
    #                         Request.status_string == JobStatus.QUEUED.value))
    #             .all()
    #         )
    #         for request in running_requests:
    #             job_handler = (self._runner_factories[request.service]
    #                            .get_runner_class(request.run_configuration)
    #                            .get_job_handler_class()
    #                            .deserialize(request.serial_job_handler))
    #             if job_handler is not None:
    #                 job_handler.cwd = request.work_dir
    #                 runner_class = (
    #                     self._runner_factories[request.service]
    #                     .get_runner_class(request.run_configuration)
    #                 )
    #                 job_handler.runner_class = runner_class
    #                 self._running_jobs[runner_class].add(
    #                     JobHandlerRequestPair(job_handler, request)
    #                 )
    #             else:
    #                 request.status = JobStatus.UNDEFINED
    #         session.commit()

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
        self.logger.info("Scheduler is watching the database.")
        while self.is_running:
            pending_requests = JobRequest.find(
                mongo.slivkadb, status=JobStatus.PENDING
            )
            runners = []
            for request in pending_requests:
                self.logger.debug('Collecting request %r', request)
                try:
                    runner_factory = self._runner_factories[request.service]
                    cwd = tempfile.mkdtemp('', '', slivka.settings.TASKS_DIR)
                    runner = runner_factory.new_runner(dict(request.inputs), cwd)
                    if runner is None:
                        request.update_db(mongo.slivkadb, status=JobStatus.REJECTED)
                        continue
                    runner.prepare()
                    runner.uuid = request.uuid
                    classpath = '%s.%s' % (
                        runner.__class__.__module__, runner.__class__.__name__
                    )
                    job = JobMetadata(
                        uuid=request.uuid,
                        service=request.service,
                        work_dir=cwd,
                        runner_class=classpath,
                        identifier=None,
                        status=JobStatus.ACCEPTED
                    )
                    job.insert(mongo.slivkadb)
                    runners.append(runner)
                    request.update_db(mongo.slivkadb, status=JobStatus.ACCEPTED)
                except Exception:
                    self.logger.exception("Creating a new runner failed.")
                    request.update_db(mongo.slivkadb, status=JobStatus.ERROR)
            self._pending_runners.extend(runners)
            self._shutdown_event.wait(0.5)

    # def _build_runner(self, request, new_cwd=True):
    #     values = {
    #         option.name: option.value
    #         for option in request.options
    #     }
    #     runner_factory = self._runner_factories[request.service]
    #     if new_cwd:
    #         cwd = tempfile.mkdtemp('', '', slivka.settings.TASKS_DIR)
    #     else:
    #         cwd = request.working_dir
    #     return runner_factory.new_runner(values, cwd)

    def _runner_observer_loop(self):
        try:
            while self.is_running:
                self._submit_runners()
                self._update_job_statuses()
                self._shutdown_event.wait(1)
        except Exception:
            self.logger.exception(
                'Critical error occurred, scheduler shuts down'
            )
            self.shutdown()

    def _submit_runners(self):
        retry_runners = []
        submit_start_time = time.time()
        counter = len(self._pending_runners)
        self.logger.info('There are %d pending runners.', counter)
        try:
            for _ in range(counter):
                if not self.is_running:
                    break
                runner = self._pending_runners.popleft()
                request = JobRequest.find_one(
                    mongo.slivkadb, uuid=runner.uuid
                )
                try:
                    job_handler = runner.start()
                    self.logger.debug('Job %s submitted' % request.uuid)
                except QueueTemporarilyUnavailableError:
                    retry_runners.append(runner)
                    self.logger.debug('Job submission deferred')
                except QueueError:
                    request.update_db(
                        mongo.slivkadb, status=JobStatus.ERROR
                    )
                    mongo.slivkadb.jobs.update_one(
                        {'uuid': runner.uuid},
                        {'$set': {'status': JobStatus.ERROR}}
                    )
                    self.logger.exception(
                        'Job cannot be scheduled due to the queue error'
                    )
                else:
                    request.update_db(
                        mongo.slivkadb, status=JobStatus.QUEUED
                    )
                    mongo.slivkadb.jobs.update_one(
                        {'uuid': runner.uuid},
                        {'$set': {
                            'status': JobStatus.QUEUED,
                            'identifier': job_handler.serialize()
                        }}
                    )
                    with self._running_jobs_lock:
                        self._running_jobs[runner.__class__].add((request, job_handler))
        finally:
            self._pending_runners.extend(retry_runners)
        self.logger.info('Submitting took %.2f s' % (time.time() - submit_start_time))

    def _update_job_statuses(self):
        self._running_jobs_lock.acquire()
        self.logger.info(
            'There are %d running jobs.',
            sum(len(j) for j in self._running_jobs.values())
        )
        try:
            for runner_class, jobs in self._running_jobs.items():
                if not self.is_running:
                    break
                if not jobs:
                    continue
                disposable_jobs = set()
                handlers = [job_handler for _, job_handler in jobs]
                try:
                    statuses = dict(runner_class.get_job_status(handlers))
                    for request, job_handler in jobs:
                        if request.status != statuses[job_handler]:
                            request.update_db(
                                mongo.slivkadb, status=statuses[job_handler]
                            )
                            mongo.slivkadb.jobs.update_one(
                                {'uuid': request.uuid},
                                {'$set': {'status': request.status}}
                            )
                        if request.status.is_finished():
                            self.logger.debug('Job %s finished' % request.uuid)
                            disposable_jobs.add((request, job_handler))
                except QueueTemporarilyUnavailableError:
                    self.logger.warning('Queue not available')
                except QueueBrokenError:
                    for request, job_handler in jobs:
                        request.update_db(
                            mongo.slivkadb, status=JobStatus.UNDEFINED
                        )
                        mongo.slivkadb.jobs.update_one(
                            {'uuid': request.uuid},
                            {'$set': {'status': JobStatus.UNDEFINED}}
                        )
                        self.logger.exception('Could not retrieve job status.')
                        disposable_jobs.add((request, job_handler))
                jobs.difference_update(disposable_jobs)
        except Exception:
            self.logger.exception(
                'Critical error occurred, scheduler shuts down'
            )
            self.stop()
            self.shutdown()
        finally:
            self._running_jobs_lock.release()

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
