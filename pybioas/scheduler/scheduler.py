import logging
import os.path
import threading
import time
import traceback

from sqlalchemy.orm import joinedload

import pybioas
from pybioas.db import check_db, Session
from pybioas.db.models import Request, Result, File
from .command.command_factory import CommandFactory
from .task_queue import queue_run, TaskQueue
from .task_queue.exceptions import ServerError
from .task_queue.job import JobStatus

logger = logging.getLogger('pybioas.Scheduler')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s %(name)s:%(threadName)s %(levelname)s: %(message)s",
    "%d %b %H:%M:%S"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


class Scheduler:

    def __init__(self):
        if not check_db():
            raise Exception("Database is not initialized.")
        self._shutdown = False
        self._tasks = set()
        self._tasks_lock = threading.Lock()
        self._command_class = {
            service: CommandFactory.get_local_command_class(service)
            for service in pybioas.settings.SERVICES
        }

    def database_poll_loop(self):
        """
        Keeps checking database for new Request records.
        """
        logger.info("Scheduler starts watching database.")
        connection_ok = TaskQueue.check_connection()
        while not self._shutdown:
            if connection_ok:
                session = Session()
                logger.debug("poll db")
                pending_requests = (
                    session.query(Request).
                    options(joinedload('options')).
                    filter(Request.status == Request.STATUS_PENDING).
                    all()
                )
                logger.debug("found {} requests".format(len(pending_requests)))
                try:
                    for request in pending_requests:
                        self.enqueue_task(request)
                except (OSError, ServerError):
                    logger.exception(traceback.format_exc())
                    connection_ok = False
                finally:
                    session.commit()
                    session.close()
            else:
                logger.info("Can't establish connection to worker. "
                            "Retry in 5 seconds.")
                connection_ok = TaskQueue.check_connection()
            time.sleep(5)

    def enqueue_task(self, request):
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
            deferred_result = queue_run(request.service, options)
            self._tasks.add(Task(deferred_result, request))
            request.status = request.STATUS_QUEUED

    def collector_loop(self):
        logger.info("Scheduler starts collecting tasks from worker.")
        connection_ok = TaskQueue.check_connection()
        while not self._shutdown:
            if connection_ok:
                session = Session()
                try:
                    for task in self._collect_finished():
                        session.query(Request). \
                            filter(Request.id == task.request_id). \
                            update({"status": Request.STATUS_COMPLETED})
                        result = task.deferred_result.result
                        res = Result(
                            return_code=result["return_code"],
                            stdout=result["stdout"],
                            stderr=result["stderr"],
                            request_id=task.request_id
                        )
                        res.output_files = [
                            File(path=path, title=os.path.basename(path))
                            for path in result['files']
                        ]
                        session.add(res)
                except OSError:
                    connection_ok = False
                finally:
                    session.commit()
                    session.close()
            else:
                logger.info("Can't establish connection to worker. "
                            "Retry in 5 seconds.")
                connection_ok = TaskQueue.check_connection()
            time.sleep(5)

    def _collect_finished(self):
        """
        Browses all running tasks and collects those which are finished.
        They are removed from the `tasks` set.
        :return: set of finished tasks
        :rtype: set[Task]
        :raise OSError:
        """
        logger.debug("collecting finished tasks")
        finished = set()
        with self._tasks_lock:
            for task in self._tasks:
                status = task.deferred_result.status
                if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    finished.add(task)
            self._tasks = self._tasks.difference(finished)
        logger.debug("found {} tasks".format(len(finished)))
        return finished

    def shutdown(self):
        self._shutdown = True


class Task:
    __slots__ = ["deferred_result", "request_id"]

    def __init__(self, deferred_result, request):
        self.deferred_result = deferred_result
        self.request_id = request.id


def start_scheduler():
    scheduler = Scheduler()
    collector_thread = threading.Thread(
        target=scheduler.collector_loop,
        name="CollectorThread"
    )
    collector_thread.start()
    poll_thread = threading.Thread(
        target=scheduler.database_poll_loop,
        name="PollThread"
    )
    poll_thread.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.debug("received shutdown signal")
        scheduler.shutdown()
    logger.info("Waiting for threads to join.")
    collector_thread.join()
    poll_thread.join()
