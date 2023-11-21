import enum


class ServiceStatus(enum.IntEnum):
    UNDEFINED = -1
    OK = 0
    WARNING = 1
    DOWN = 2
