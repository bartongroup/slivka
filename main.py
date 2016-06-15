#!usr/bin/env

import sys


if "--worker" in sys.argv:
    from scheduler.task_queue.worker import start_worker
    start_worker()
elif "--server" in sys.argv:
    from server.serverapp import app
    app.run(host='localhost', port=8080, debug=True)
elif "--initdb" in sys.argv:
    from db import create_db
    create_db()
