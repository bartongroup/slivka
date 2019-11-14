import sys
import types
from urllib.parse import quote_plus

import pymongo.database

import slivka
from slivka.utils import lazy_property


def _build_mongodb_uri(*, host=None, socket=None, username=None,
                       password=None, database):
    uri = 'mongodb://'
    if username is not None:
        if password is None:
            uri += '%s@' % quote_plus(username)
        else:
            uri += '%s:%s@' % (quote_plus(username), quote_plus(password))
    if host is not None:
        uri += host
    else:
        uri += quote_plus(socket)
    return uri, database


class _DBModule(types.ModuleType):
    def __init__(self):
        super().__init__(__name__)
        self.__path__ = __path__
        self.__file__ = __file__
        self._dbname = None

    @lazy_property
    def mongo(self):
        if isinstance(slivka.settings.MONGODB, str):
            host, self._dbname = slivka.settings.MONGODB.rsplit('/', 1)
        else:
            host, self._dbname = _build_mongodb_uri(**slivka.settings.MONGODB)
        return pymongo.MongoClient(host)

    @lazy_property
    def database(self):
        return self.mongo[self._dbname]


mongo = ...  # type: pymongo.MongoClient
database = ... # type: pymongo.database.Database

sys.modules[__name__] = _DBModule()
