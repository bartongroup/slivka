import sys
import types

from pymongo import MongoClient

import slivka
from slivka.utils import lazy_property


class _DBModule(types.ModuleType):
    def __init__(self):
        super().__init__(__name__)
        self.__path__ = __path__
        self.__file__ = __file__

    @lazy_property
    def mongo(self):
        return MongoClient(slivka.settings.MONGODB_ADDR)


mongo = ...  # type: MongoClient

sys.modules[__name__] = _DBModule()
