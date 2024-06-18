import datetime
import operator
from datetime import datetime, date
from typing import List

import attr
import attrs
import pymongo

import slivka.db
from slivka.consts import ServiceStatus as Status


@attr.s()
class ServiceStatusInfo:
    UNDEFINED = Status.UNDEFINED
    OK = Status.OK
    WARNING = Status.WARNING
    DOWN = Status.DOWN

    service = attr.ib()
    runner = attr.ib()
    status = attr.ib(converter=Status)
    message = attr.ib(default="")
    timestamp = attr.ib(factory=datetime.now)


class ServiceStatusMongoDBRepository:
    _collection = 'servicestate'

    def __init__(self, database=None):
        if database is None:
            database = slivka.db.database
        self._db = database

    def insert(self, service_status: ServiceStatusInfo):
        doc = {
            'service': service_status.service,
            'runner': service_status.runner,
            'state': service_status.status,
            'message': service_status.message,
            'timestamp': service_status.timestamp
        }
        self._db[self._collection].insert_one(doc)

    def list_all(self, service=None, runner=None) -> List[ServiceStatusInfo]:
        filters = {}
        if service is not None:
            filters['service'] = service
        if runner is not None:
            filters['runner'] = runner
        cursor = self._db[self._collection].find(filters)
        cursor = cursor.sort('timestamp', pymongo.DESCENDING)
        return [
            ServiceStatusInfo(
                service=d['service'],
                runner=d['runner'],
                status=d['state'],
                message=d['message'],
                timestamp=d['timestamp']
            )
            for d in cursor
        ]

    def list_current(self, service=None, runner=None) -> List[ServiceStatusInfo]:
        filters = {}
        if service is not None:
            filters['service'] = service
        if runner is not None:
            filters['runner'] = runner
        cursor = self._db[self._collection].aggregate([
            {'$match': filters},
            {'$sort': {'timestamp': pymongo.DESCENDING}},
            {'$group': {
                '_id': {
                    'service': '$service',
                    'runner': '$runner',
                },
                'status': {'$first': {
                    'status': '$state',
                    'message': '$message',
                    'timestamp': '$timestamp'
                }}
            }}
        ])
        return sorted(
            (
                ServiceStatusInfo(
                    service=d['_id']['service'],
                    runner=d['_id']['runner'],
                    status=d['status']['status'],
                    message=d['status']['message'],
                    timestamp=d['status']['timestamp']
                )
                for d in cursor
            ),
            key=operator.attrgetter('timestamp'),
            reverse=True
        )


ServiceStatusRepository = ServiceStatusMongoDBRepository


@attrs.define
class UsageStats:
    month: date
    service: str
    count: int


class UsageStatsMongoDBRepository:
    __requests_collection = "requests"

    def __init__(self, database=None):
        if database is None:
            database = slivka.db.database
        self._database = database

    def list_all(self) -> List[UsageStats]:
        collection = self._database[self.__requests_collection]
        aggregation = collection.aggregate([
            {"$group": {
                "_id": {
                    "month": {
                        "$dateTrunc": {"date": "$timestamp", "unit": "month"}
                    },
                    "service": "$service",
                },
                "count": {"$count": {}}
            }},
            {"$sort": {"_id.month": 1}}
        ])
        return [
            UsageStats(
                month=date(
                    entry["_id"]["month"].year,
                    entry["_id"]["month"].month,
                    1
                ),
                service=entry["_id"]["service"],
                count=entry["count"]
            )
            for entry in aggregation
        ]


UsageStatsRepository = UsageStatsMongoDBRepository
