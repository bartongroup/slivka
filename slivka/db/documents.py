import os
from base64 import urlsafe_b64encode, urlsafe_b64decode
from collections.abc import MutableMapping
from datetime import datetime

import attrs
import pymongo
from bson import ObjectId

# importing slivka.db.helpers causes circular dependency
import slivka
from slivka import JobStatus, consts
from slivka.utils import deprecated, alias_property


class _AttrsDict(MutableMapping):
    __slots__ = ()

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except (AttributeError, TypeError):
            raise KeyError(key)

    def __setitem__(self, key, value):
        try:
            setattr(self, key, value)
        except (AttributeError, TypeError):
            raise KeyError(key)

    def __delitem__(self, key):
        try:
            delattr(self, key)
        except (AttributeError, TypeError):
            raise KeyError(key)

    def __iter__(self):
        return (
            field.name
            for field in attrs.fields(type(self))
            if hasattr(self, field.name)
        )

    def __len__(self):
        return sum(1 for _ in iter(self))


@attrs.define(init=False)
class MongoDocument(_AttrsDict):
    # MongoDocument and its derivatives must be defined with init=False
    # and initialization to be delegated to this class' __init__.
    # Otherwise, attrs does not allow optional _id field to be left
    # uninitialised.
    # Missing _id key is required by pymongo to assign _id to new
    # documents correctly.

    __collection__ = None
    _id: ObjectId = attrs.field(init=False)

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if cls.__collection__ is None:
            raise AttributeError("Subclasses must specify __collection__ property")

    def __init__(self, *args, _id=attrs.NOTHING, **kwargs):
        super().__init__()
        if _id is not attrs.NOTHING:
            self._id = _id
        self.__attrs_init__(*args, **kwargs)

    @property
    def id(self) -> ObjectId:
        return self._id

    @property
    def b64id(self) -> str:
        return urlsafe_b64encode(self._id.binary).decode()

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
        collection = database[cls.__collection__]
        item = collection.find_one(kwargs)
        return cls(**item) if item is not None else None

    @classmethod
    def find(cls, database, query=(), **kwargs):
        query = dict(query, **kwargs)
        cursor = database[cls.__collection__].find(query)
        return (cls(**kwargs) for kwargs in cursor)

    @deprecated
    def insert(self, database):
        slivka.db.helpers.insert_one(database, self)

    @deprecated
    def update_self(self, database, values=(), **kwargs):
        super().update(values, **kwargs)
        slivka.db.helpers.push_one(database, self)

    @classmethod
    @deprecated
    def update_one(cls, database, filter, values):
        database[cls.__collection__].update_one(
            filter, {'$set': values}
        )

    def __hash__(self):
        return hash(self._id)


@attrs.define(kw_only=True, init=False)
class JobRequest(MongoDocument, _AttrsDict):
    __collection__ = 'requests'

    @attrs.define(kw_only=True)
    class Job(_AttrsDict):
        work_dir: str
        job_id: str
        cwd = alias_property("work_dir")

    service: str = attrs.field()
    inputs: dict = attrs.field()

    timestamp: datetime = attrs.field(factory=datetime.now)
    submission_time = alias_property("timestamp")
    completion_time: datetime = attrs.field(default=None)

    status: JobStatus = attrs.field(default=JobStatus.PENDING, converter=JobStatus)
    state = alias_property("status")

    runner: str = attrs.field(default=None)
    job: Job = attrs.field(
        default=None,
        converter=attrs.converters.optional(lambda it: JobRequest.Job(**it))
    )


@attrs.define(kw_only=True, init=False)
class CancelRequest(MongoDocument, _AttrsDict):
    __collection__ = 'cancelrequest'

    job_id: str


@attrs.define(kw_only=True, init=False)
class UploadedFile(MongoDocument, _AttrsDict):
    __collection__ = 'files'

    title: str
    media_type: str
    path: str

    @property
    @deprecated
    def uuid(self):
        return self.b64id

    @property
    def basename(self):
        return os.path.basename(self.path)


@deprecated
@attrs.define(kw_only=True, init=False)
class ServiceState(MongoDocument, _AttrsDict):
    __collection__ = 'servicestate'

    State = consts.ServiceStatus

    UNDEFINED = State.UNDEFINED
    OK = State.OK
    WARNING = State.WARNING
    DOWN = State.DOWN

    service: str
    runner: str
    state: State = attrs.field(default=State.OK, converter=State)
    status = alias_property("state")
    message: str = attrs.field(default="")
    timestamp: datetime = attrs.field(factory=datetime.now)
