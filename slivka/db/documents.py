import os
import pathlib
from base64 import b64encode
from datetime import datetime
from uuid import uuid4

import bson
import pymongo

from slivka import JobStatus


def b64_uuid4():
    return b64encode(uuid4().bytes, altchars=b'_-').rstrip(b'=').decode()


class MongoDocument(bson.SON):
    __collection__ = None

    @classmethod
    def get_collection(cls, database) -> pymongo.collection.Collection:
        return database[cls.__collection__]

    def __getattr__(self, item):
        return self[item]

    def __setattr__(self, key, value):
        if key == '_id':
            raise KeyError('_id cannot be changed')
        super().__setattr__(key, value)

    @classmethod
    def find_one(cls, database, **kwargs):
        item = database[cls.__collection__].find_one(kwargs)
        return cls(**item) if item is not None else None

    @classmethod
    def find(cls, database, query=(), **kwargs):
        query = dict(query, **kwargs)
        cursor = database[cls.__collection__].find(query)
        return (cls(**kwargs) for kwargs in cursor)

    def insert(self, database):
        database[self.__collection__].insert_one(self)

    def update_self(self, database, values=(), **kwargs):
        super().update(values, **kwargs)
        database[self.__collection__].update_one(
            {'_id': self._id},
            {'$set': dict(values, **kwargs)}
        )

    @classmethod
    def update_one(cls, database, filter, values):
        database[cls.__collection__].update_one(
            filter, {'$set': values}
        )

    def __eq__(self, other: 'MongoDocument'):
        return self['_id'] == other['_id']

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

    @property
    def status(self) -> JobStatus:
        return JobStatus(self['status'])


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

    @property
    def status(self) -> JobStatus:
        return JobStatus(self['status'])


class UploadedFile(MongoDocument):
    __collection__ = 'files'

    def __init__(self, **kwargs):
        kwargs.setdefault('uuid', b64_uuid4())
        kwargs.setdefault('basename', os.path.basename(kwargs['path']))
        super().__init__(**kwargs)

    def get_path(self):
        return pathlib.Path(self['path'])
