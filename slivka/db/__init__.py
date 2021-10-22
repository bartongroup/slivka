import sys
import types
from urllib.parse import quote_plus

import pymongo.database

import slivka.conf
from slivka.utils import cached_property


def _build_mongodb_uri(host=None, socket=None, username=None, password=None):
    uri = 'mongodb://'
    if username is not None:
        if password is None:
            uri += '%s@' % quote_plus(username)
        else:
            uri += '%s:%s@' % (quote_plus(username), quote_plus(password))
    if socket is not None:
        uri += quote_plus(socket)
    elif host is not None:
        uri += host
    else:
        raise ValueError("Either 'host' or 'socket' must be provided.")
    return uri


class _DBModule(types.ModuleType):
    def __init__(self):
        super().__init__(__name__)
        self.__path__ = __path__
        self.__file__ = __file__

    @cached_property
    def mongo(self):
        cfg = slivka.conf.settings.mongodb
        mongo_uri = _build_mongodb_uri(
            host=cfg.host, socket=cfg.socket,
            username=cfg.username, password=cfg.password
        )
        return pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)

    @cached_property
    def database(self):
        return self.mongo[slivka.conf.settings.mongodb.database]


mongo = ...  # type: pymongo.MongoClient
database = ...  # type: pymongo.database.Database

sys.modules[__name__] = _DBModule()
