from slivka.scheduler.limits import LimitsBase


class PydummyLimits(LimitsBase):

    configurations = ['local']

    def limit_local(self, values):
        return True
