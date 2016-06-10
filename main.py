#!usr/bin/env

import sys


if "--worker" in sys.argv:
    from scheduler.task_queue import start_worker
    start_worker()
elif "--server" in sys.argv:
    from server.serverapp import app
    app.run(host='localhost', port=8080, debug=True)
