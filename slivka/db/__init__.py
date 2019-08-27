import sys
import types

from pymongo import MongoClient

import slivka


class _DBModule(types.ModuleType):
    def __init__(self):
        super().__init__(__name__)
        self.__path__ = __path__
        self.__file__ = __file__

    def __getattr__(self, item):
        if item is 'mongo':
            val = MongoClient(slivka.settings.MONGODB_ADDR)
        else:
            try:
                val = globals()[item]
            except KeyError:
                raise AttributeError(
                    "module '%s' has no attribute '%s'" % (__name__, item)
                )
        self.__dict__[item] = val
        return val


mongo = ...  # type: MongoClient

sys.modules[__name__] = _DBModule()
