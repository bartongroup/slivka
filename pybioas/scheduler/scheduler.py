import logging
import os.path
import threading
import time
from configparser import ConfigParser

import jsonschema
import yaml
from sqlalchemy.orm import joinedload

import pybioas.utils
from pybioas.db import Session
from pybioas.db.models import Request, Result, File
from .executors import Executor, Job
from .task_queue import ServerError, QueueServer


class Scheduler:

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._shutdown_event = threading.Event()
        self._tasks = set()
        self._tasks_lock = threading.Lock()
        self._set_executors()
        self._poll_thread = threading.Thread(
            target=self.database_poll_loop,
            name="PollThread"
        )
        self._collector_thread = threading.Thread(
            target=self.collector_loop,
            name="PollThread"
        )

    def _set_executors(self):
        parser = ConfigParser()
        parser.optionxform = lambda option: option
        with open(pybioas.settings.SERVICE_INI) as file:
            parser.read_file(file)
        self._executors = {}
        for service in parser.sections():
            with open(parser.get(service, 'config')) as file:
                conf_data = yaml.load(file)
            jsonschema.validate(conf_data, pybioas.utils.CONF_SCHEMA)
            self._executors[service] = Executor.make_from_conf(conf_data)

    def start(self, async=False):
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

    def shutdown(self):
        self._shutdown_event.set()
        self._collector_thread.join()
        self._poll_thread.join()

    def get_executor(self, service, configuration):
        return self._executors[service][configuration]

    def database_poll_loop(self):
        """
        Keeps checking database for new Request records.
        """
        self.logger.info("Scheduler starts watching database.")
        connection_ok = QueueServer.check_connection()
        if connection_ok:
            self.logger.info("Connected to worker.")
        while self.is_running:
            if connection_ok:
                session = Session()
                pending_requests = (
                    session.query(Request).
                    options(joinedload('options')).
                    filter(Request.status == Request.STATUS_PENDING).
                    all()
                )
                if len(pending_requests) > 0:
                    self.logger.debug(
                        "Found %d requests", len(pending_requests)
                    )
                try:
                    for request in pending_requests:
                        self.submit_request(request)
                except (OSError, ServerError):
                    self.logger.exception("Connection lost.")
                    connection_ok = False
                finally:
                    session.commit()
                    session.close()
            else:
                self.logger.info("Can't establish connection to worker. "
                                 "Retry in 5 seconds.")
                connection_ok = QueueServer.check_connection()
                if connection_ok:
                    self.logger.info("Connected to worker.")
            self._shutdown_event.wait(5)

    def submit_request(self, request):
        """
        Enqueues a new task in the local queue.
        :param request: job request
        :type request: Request
        :raise OSError
        :raise ServerError
        """
        options = {
            option.name: option.value
            for option in request.options
        }
        with self._tasks_lock:
            executor = self.get_executor(request.service, 'local')
            job = executor(options)
            self._tasks.add(Task(job, request.id))
            request.status = request.STATUS_QUEUED

    def collector_loop(self):
        self.logger.info("Scheduler starts collecting tasks.")
        connection_ok = QueueServer.check_connection()
        if connection_ok:
            self.logger.info("Connected to worker.")
        while self.is_running:
            if connection_ok:
                session = Session()
                # noinspection PyBroadException
                try:
                    for task in self._collect_finished():
                        (session.query(Request).
                            filter(Request.id == task.request_id).
                            update({"status": Request.STATUS_COMPLETED}))
                        result = task.job.result
                        self._logger.debug(
                            "Result of %s: %s",
                            task.request_id, result,
                        )
                        res = Result(
                            return_code=result.return_code,
                            stdout=result.stdout,
                            stderr=result.stderr,
                            request_id=task.request_id
                        )
                        res.output_files = [
                            File(path=path, title=os.path.basename(path))
                            for path in task.job.file_results
                        ]
                        session.add(res)
                except OSError:
                    self.logger.exception("Connection lost.")
                    connection_ok = False
                except:
                    self._logger.critical(
                        "Critical error occurred, scheduler shuts down.",
                        exc_info=True
                    )
                    self.shutdown()
                finally:
                    session.commit()
                    session.close()
            else:
                self.logger.info("Can't establish connection to worker. "
                                 "Retry in 5 seconds.")
                connection_ok = QueueServer.check_connection()
                if connection_ok:
                    self.logger.info("Connected to worker.")
            self._shutdown_event.wait(5)

    def _collect_finished(self):
        """
        Browses all running tasks and collects those which are finished.
        They are removed from the `tasks` set.
        :return: set of finished tasks
        :rtype: set[Task]
        :raise OSError:
        """
        self.logger.debug("Collecting finished tasks")
        with self._tasks_lock:
            finished = {task for task in self._tasks if task.job.is_finished()}
            self._tasks.difference_update(finished)
        self.logger.debug("Found %d tasks", len(finished))
        return finished

    @property
    def logger(self):
        return self._logger

    @property
    def is_running(self):
        return not self._shutdown_event.is_set()


class Task:
    __slots__ = ['job', 'request_id']

    def __init__(self, job, request_id):
        """
        :type job: Job
        :type request_id: int
        """
        self.job = job
        self.request_id = request_id
