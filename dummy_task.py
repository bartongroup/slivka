import time

from task_queue import RunnableTask


class C(RunnableTask):
    def run(self, *args, **kwargs):
        print("going to sleep")
        time.sleep(10)
        print("I slept well")
        return "Hello!"
