import time

from task_queue import RunnableTask


class C(RunnableTask):
    def run(self, *args, **kwargs):
        time.sleep(1)
        return "Hello"
