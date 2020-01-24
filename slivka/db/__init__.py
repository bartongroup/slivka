import sys
import types
from urllib.parse import quote_plus

import pymongo.database

import slivka.conf
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

    @lazy_property
    def mongo(self):
        host, _ = slivka.conf.settings.mongodb
        return pymongo.MongoClient(host)

    @lazy_property
    def database(self):
        _, dbname = slivka.conf.settings.mongodb
        return self.mongo[dbname]


mongo = ...  # type: pymongo.MongoClient
database = ... # type: pymongo.database.Database

sys.modules[__name__] = _DBModule()
