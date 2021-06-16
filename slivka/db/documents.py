import enum
import os
from base64 import urlsafe_b64encode as b64encode
from datetime import datetime
from uuid import uuid4

import pymongo
from bson import ObjectId

from slivka import JobStatus
from slivka.utils import deprecated


def b64_uuid4():
    return b64encode(uuid4().bytes).rstrip(b'=').decode()


class MongoDocument(dict):
    __collection__ = None

    def _get_id(self) -> ObjectId: return self.get('_id')
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

    def __init__(self, *,
                 service,
                 inputs,
                 uuid=None,
                 timestamp=None,
                 status=None,
                 runner=None,
                 **kwargs):
        super().__init__(
            service=service,
            inputs=inputs,
            uuid=uuid if uuid is not None else b64_uuid4(),
            timestamp=timestamp if timestamp is not None else datetime.now(),
            status=status if status is not None else JobStatus.PENDING,
            runner=runner,
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

    def _get_runner(self): return self['runner']
    def _set_runner(self, val): self['runner'] = val
    runner = property(_get_runner, _set_runner)


class CancelRequest(MongoDocument):
    __collection__ = 'cancelrequest'

    def __init__(self, uuid, **kwargs):
        super().__init__(uuid=uuid, **kwargs)

    uuid = property(lambda self: self['uuid'])


class JobMetadata(MongoDocument):
    __collection__ = 'jobs'

    def __init__(self, *,
                 uuid,
                 service,
                 runner,
                 work_dir,
                 job_id,
                 status,
                 **kwargs):
        super().__init__(
            uuid=uuid,
            service=service,
            runner=runner,
            work_dir=work_dir,
            job_id=job_id,
            status=status,
            **kwargs
        )

    uuid = property(lambda self: self['uuid'])
    service = property(lambda self: self['service'])
    runner = property(lambda self: self['runner'])
    work_dir = property(lambda self: self['work_dir'])
    cwd = work_dir
    job_id = property(lambda self: self['job_id'])

    def _get_state(self): return JobStatus(self['status'])
    def _set_state(self, val): self['status'] = val
    state = property(_get_state, _set_state)
    status = property(_get_state, _set_state)


class UploadedFile(MongoDocument):
    __collection__ = 'files'

    def __init__(self, *,
                 title=None,
                 media_type=None,
                 path,
                 **kwargs):
        super().__init__(
            title=title,
            media_type=media_type,
            path=path,
            **kwargs
        )

    @property
    @deprecated
    def uuid(self):
        return self.b64id

    def _get_b64id(self):
        return b64encode(self._get_id().binary).decode()

    b64id = property(_get_b64id)
    title = property(lambda self: self['title'])
    media_type = property(lambda self: self['media_type'])
    path = property(lambda self: self['path'])

    def get_basename(self): return os.path.basename(self['path'])
    basename = property(get_basename)


class ServiceState(MongoDocument):
    __collection__ = 'servicestate'

    class State(enum.IntEnum):
        OK = 0
        WARNING = 1
        DOWN = 2

    OK = State.OK
    WARNING = State.WARNING
    DOWN = State.DOWN

    def __init__(self, *,
                 service,
                 runner,
                 state=State.OK,
                 message="",
                 timestamp=None,
                 **kwargs):
        super().__init__(
            service=service,
            runner=runner,
            state=state,
            message=message,
            timestamp=timestamp or datetime.now(),
            **kwargs
        )

    service = property(lambda self: self['service'])
    runner = property(lambda self: self['runner'])

    def _get_state(self): return self.State(self['state'])
    def _set_state(self, val): self['state'] = val
    state = property(_get_state, _set_state)

    def _get_timestamp(self): return self['timestamp']
    def _set_timestamp(self, val): self['timestamp'] = val
    def reset_timestamp(self): self['timestamp'] = datetime.now()
    timestamp = property(_get_timestamp, _set_timestamp)

    def _get_message(self): return self['message']
    def _set_message(self, val): self['message'] = val
    message = property(_get_message, _set_message)
