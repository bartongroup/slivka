from pybioas.scheduler.executors import JobLimits


class PydummyLimits(JobLimits):

    configurations = ['local']

    def limit_local(self, values):
        return True
