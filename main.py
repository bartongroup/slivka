#!usr/bin/env

import sys


if "--worker" in sys.argv:
    from task_queue.worker import start_worker
    start_worker()
