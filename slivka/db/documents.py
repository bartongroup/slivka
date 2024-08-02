import enum
import os
from base64 import urlsafe_b64encode, urlsafe_b64decode
from datetime import datetime

import pymongo
from bson import ObjectId

from slivka import JobStatus, consts
from slivka.utils import deprecated


class MongoDocument(dict):
    __collection__ = None

    def _get_id(self) -> ObjectId: return self.get('_id')
    id = property(fget=_get_id)

    def _get_b64id(self) -> str:
        return urlsafe_b64encode(self._get_id().binary).decode()
    b64id = property(_get_b64id)

    @classmethod
    def get_collection(cls, database) -> pymongo.collection.Collection:
        return database[cls.__collection__]
    collection = get_collection

    @classmethod
    def find_one(cls, database, **kwargs):
        _id = kwargs.pop('id', None)
        if isinstance(_id, ObjectId):
            kwargs['_id'] = _id
        elif isinstance(_id, (str, bytes)):
            if len(_id) == 16:  # b64 encoded
                _id = urlsafe_b64decode(_id)
            elif not ((len(_id) == 12 and isinstance(_id, bytes)) or
                      (len(_id) == 24 and isinstance(_id, str))):
                # invalid id, neither raw bytes nor hex string
                return None
            kwargs['_id'] = ObjectId(_id)
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

    class Job(dict):
        def __init__(self, *,
                     work_dir,
                     job_id):
            dict.__init__(
                self,
                work_dir=work_dir,
                job_id=job_id
            )

        work_dir = property(lambda self: self['work_dir'])
        cwd = work_dir
        job_id = property(lambda self: self['job_id'])

    def __init__(self, *,
                 service,
                 inputs,
                 timestamp=None,
                 completion_time=None,
                 status=None,
                 runner=None,
                 job=None,
                 **kwargs):
        super().__init__(
            service=service,
            inputs=inputs,
            timestamp=timestamp if timestamp is not None else datetime.now(),
            completion_time=completion_time,
            status=status if status is not None else JobStatus.PENDING,
            runner=runner,
            job=self.Job(**job) if job else None,
            **kwargs
        )

    service = property(lambda self: self['service'])
    inputs = property(lambda self: self['inputs'])
    timestamp = property(lambda self: self['timestamp'])
    submission_time = property(lambda self: self['timestamp'])

    def _get_completion_time(self): return self['completion_time']
    def _set_completion_time(self, val): self['completion_time'] = val
    completion_time = property(_get_completion_time, _set_completion_time)

    def _get_status(self): return JobStatus(self['status'])
    def _set_status(self, val): self['status'] = val
    state = property(_get_status, _set_status)
    status = property(_get_status, _set_status)

    def _get_runner(self): return self['runner']
    def _set_runner(self, val): self['runner'] = val
    runner = property(_get_runner, _set_runner)

    def _get_job(self): return self['job'] and JobRequest.Job(**self['job'])
    def _set_job(self, val): self['job'] = val
    job = property(_get_job, _set_job)


class CancelRequest(MongoDocument):
    __collection__ = 'cancelrequest'

    def __init__(self, job_id, **kwargs):
        super().__init__(job_id=job_id, **kwargs)

    job_id = property(lambda self: self['job_id'])


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

    title = property(lambda self: self['title'])
    media_type = property(lambda self: self['media_type'])
    path = property(lambda self: self['path'])

    def get_basename(self): return os.path.basename(self['path'])
    basename = property(get_basename)


class ServiceState(MongoDocument):
    __collection__ = 'servicestate'

    State = consts.ServiceStatus

    UNDEFINED = State.UNDEFINED
    OK = State.OK
    WARNING = State.WARNING
    DOWN = State.DOWN

    @deprecated
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
    status = property(_get_state, _set_state)

    def _get_timestamp(self): return self['timestamp']
    def _set_timestamp(self, val): self['timestamp'] = val
    def reset_timestamp(self): self['timestamp'] = datetime.now()
    timestamp = property(_get_timestamp, _set_timestamp)

    def _get_message(self): return self['message']
    def _set_message(self, val): self['message'] = val
    message = property(_get_message, _set_message)
