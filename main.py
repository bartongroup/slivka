#!usr/bin/env

import sys

from task_queue import queue_run


def start_worker():
    from task_queue.worker import Worker

    w = Worker()
    w.listen()


def test_worker():
    from dummy_task import C
    c = C()
    res = queue_run(c)
    print(res)

if "--worker" in sys.argv:
    start_worker()
else:
    test_worker()
