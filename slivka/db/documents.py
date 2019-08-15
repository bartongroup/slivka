import os
import pathlib
from base64 import b64encode
from datetime import datetime
from uuid import uuid4

import bson

from slivka import JobStatus


def b64_uuid4():
    return b64encode(uuid4().bytes, altchars=b'_-').rstrip(b'=').decode()


class MongoDocument(bson.SON):
    __collection__ = None

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
    def find(cls, database, **kwargs):
        cursor = database[cls.__collection__].find(kwargs)
        return (cls(**kwargs) for kwargs in cursor)

    def insert(self, database):
        database[self.__collection__].insert_one(self)

    def update_db(self, database, other=(), **kwargs):
        if '_id' in kwargs or '_id' in other:
            raise KeyError('_id cannot be changed')
        super().update(other, **kwargs)
        data = dict(other)
        data.update(**kwargs)
        database[self.__collection__].update_one(
            {'_id': self._id},
            {'$set': data}
        )

    def __hash__(self):
        return hash(self['_id'])


class JobRequest(MongoDocument):
    __collection__ = 'requests'

    __required = ('service', 'inputs')

    def __init__(self, **kwargs):
        kwargs.setdefault('uuid', b64_uuid4())
        kwargs.setdefault('timestamp', datetime.now())
        kwargs.setdefault('status', JobStatus.PENDING)
        if not all(k in kwargs for k in self.__required):
            raise ValueError("Required parameter missing.")
        super().__init__(**kwargs)

    @property
    def status(self) -> JobStatus:
        return JobStatus(self['status'])


class JobMetadata(MongoDocument):
    __collection__ = 'jobs'

    __required = ('uuid', 'service', 'work_dir',
                  'runner_class', 'identifier', 'status')

    def __init__(self, **kwargs):
        if not all(k in kwargs for k in self.__required):
            raise ValueError("Required parameter missing.")
        super().__init__(**kwargs)

    def __getattr__(self, item):
        return self[item]

    @property
    def status(self) -> JobStatus:
        return JobStatus(self['status'])


class UploadedFile(MongoDocument):
    __collection__ = 'files'

    def __init__(self, **kwargs):
        kwargs.setdefault('uuid', b64_uuid4())
        kwargs.setdefault('basename', os.path.basename(kwargs['path']))
        super().__init__(**kwargs)

    @property
    def path_obj(self):
        return pathlib.Path(self['path'])
