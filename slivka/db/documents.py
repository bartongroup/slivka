import os
from base64 import b64encode

import bson
import pathlib
import pymongo
from datetime import datetime
from uuid import uuid4

from slivka import JobStatus
from slivka.utils import deprecated


def b64_uuid4():
    return b64encode(uuid4().bytes, altchars=b'_-').rstrip(b'=').decode()


class MongoDocument(bson.SON):
    __collection__ = None

    def _get_id(self): return self['_id']
    id = property(fget=_get_id)

    @classmethod
    def get_collection(cls, database) -> pymongo.collection.Collection:
        return database[cls.__collection__]
    collection = get_collection

    @classmethod
    def find_one(cls, database, **kwargs):
        item = database[cls.__collection__].find_one(kwargs)
        return cls(**item) if item is not None else None

    @classmethod
    def find(cls, database, query=(), **kwargs):
        query = dict(query, **kwargs)
        cursor = database[cls.__collection__].find(query)
        return (cls(**kwargs) for kwargs in cursor)

    @deprecated
    def insert(self, database):
        database[self.__collection__].insert_one(self)

    @deprecated
    def update_self(self, database, values=(), **kwargs):
        super().update(values, **kwargs)
        database[self.__collection__].update_one(
            {'_id': self._get_id()},
            {'$set': dict(values, **kwargs)}
        )

    @classmethod
    @deprecated
    def update_one(cls, database, filter, values):
        database[cls.__collection__].update_one(
            filter, {'$set': values}
        )

    def __hash__(self):
        return hash(self['_id'])


class JobRequest(MongoDocument):
    __collection__ = 'requests'

    def __init__(self,
                 service,
                 inputs,
                 uuid=None,
                 timestamp=None,
                 status=None,
                 **kwargs):
        super().__init__(
            service=service,
            inputs=inputs,
            uuid=uuid if uuid is not None else b64_uuid4(),
            timestamp=timestamp if timestamp is not None else datetime.now(),
            status=status if status is not None else JobStatus.PENDING,
            **kwargs
        )

    service = property(lambda self: self['service'])
    inputs = property(lambda self: self['inputs'])
    uuid = property(lambda self: self['uuid'])
    timestamp = property(lambda self: self['timestamp'])

    def _get_state(self): return JobStatus(self['status'])
    def _set_state(self, val): self['status'] = val
    state = property(_get_state, _set_state)
    status = property(_get_state, _set_state)


class JobMetadata(MongoDocument):
    __collection__ = 'jobs'

    def __init__(self,
                 uuid,
                 service,
                 work_dir,
                 runner_class,
                 job_id,
                 status,
                 **kwargs):
        super().__init__(
            uuid=uuid,
            service=service,
            work_dir=work_dir,
            runner_class=runner_class,
            job_id=job_id,
            status=status,
            **kwargs
        )

    uuid = property(lambda self: self['uuid'])
    service = property(lambda self: self['service'])
    work_dir = property(lambda self: self['work_dir'])
    cwd = work_dir
    runner_class = property(lambda self: self['runner_class'])
    job_id = property(lambda self: self['job_id'])

    def _get_state(self): return JobStatus(self['status'])
    def _set_state(self, val): self['status'] = val
    state = property(_get_state, _set_state)
    status = property(_get_state, _set_state)


class UploadedFile(MongoDocument):
    __collection__ = 'files'

    def __init__(self, **kwargs):
        kwargs.setdefault('uuid', b64_uuid4())
        kwargs.setdefault('basename', os.path.basename(kwargs['path']))
        super().__init__(**kwargs)

    def get_path(self):
        return pathlib.Path(self['path'])
