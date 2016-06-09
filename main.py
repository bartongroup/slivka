#!usr/bin/env

import sys


if "--worker" in sys.argv:
    from scheduler.task_queue import start_worker
    start_worker()
