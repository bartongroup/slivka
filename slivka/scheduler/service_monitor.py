from datetime import datetime

import attr
from slivka.consts import ServiceStatus as Status


@attr.s()
class ServiceStatusInfo:
    OK = Status.OK
    WARNING = Status.WARNING
    DOWN = Status.DOWN

    service = attr.ib()
    runner = attr.ib()
    status = attr.ib(converter=Status)
    message = attr.ib(default="")
    timestamp = attr.ib(factory=datetime.now)
