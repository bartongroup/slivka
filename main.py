#!usr/bin/env

import sys
import time

from task_queue import queue_run


def test_worker():
    from dummy_task import C
    c = C()
    res = queue_run(c)
    print(res)
    print(res.status)
    print(res.result)
    time.sleep(11)
    print(res.status)
    print(res.result)

if "--worker" in sys.argv:
    from task_queue.worker import start_worker
    start_worker()
else:
    test_worker()
