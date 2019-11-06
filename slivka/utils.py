import enum
import os
from collections import OrderedDict

import yaml.resolver

try:
    import simplejson as json
except ImportError:
    import json


# ## Singleton metaclass ##

class Singleton(type):
    __instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls.__instances:
            cls.__instances[cls] = super().__call__(*args, **kwargs)
        return cls.__instances[cls]

    @property
    def instance(cls):
        return cls()


# lazy property decorator

# noinspection PyPep8Naming
class lazy_property:
    def __init__(self, initializer):
        self._init = initializer

    def __get__(self, instance, owner):
        if instance is None:
            return self
        val = self._init(instance)
        name = self._init.__name__
        if name.startswith('__') and not name.endswith('__'):
            name = '_' + owner.__name__ + name
        instance.__dict__[name] = val
        return val


# ## Yaml loaders using OrderedDict ##

class SafeTranscludingOrderedYamlLoader(yaml.SafeLoader):
    def __init__(self, stream):
        try:
            self.root_path = os.path.dirname(stream.name)
        except AttributeError:
            self.root_path = os.path.curdir
        self.root_path = os.path.abspath(self.root_path)
        super().__init__(stream)


def _include_constructor(loader: SafeTranscludingOrderedYamlLoader, node: yaml.Node):
    val = loader.construct_scalar(node).split('#', 1)
    fn, path = val if len(val) == 2 else (val[0], '/')
    fn = os.path.join(loader.root_path, fn)
    with open(fn) as f:
        obj = yaml.load(f, Loader=loader.__class__)
    for key in filter(None, path.split('/')):
        obj = obj[key]
    return obj


def _mapping_constructor(loader, node):
    loader.flatten_mapping(node)
    return OrderedDict(loader.construct_pairs(node))


SafeTranscludingOrderedYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _mapping_constructor
)

SafeTranscludingOrderedYamlLoader.add_constructor(
    '!include', _include_constructor
)


class JobStatus(enum.IntEnum):
    PENDING = 1  # Request submitted to the database but not processed yet
    REJECTED = 2  # Request rejected due to input parameter limitations
    ACCEPTED = 3  # Job was accepted but has not been sent to the queuing system yet
    QUEUED = 4  # Job successfully submitted to the queuing system
    RUNNING = 5  # Job is being executed
    COMPLETED = 6  # Job finished successfully with 0 status code
    INTERRUPTED = 7  # Job has been interrupted during execution
    DELETED = 8  # Job has been deleted from the queuing system
    FAILED = 9  # Job finished with non-0 status code
    ERROR = 10  # Internal error
    UNKNOWN = 11

    def is_finished(self):
        return self not in (JobStatus.PENDING, JobStatus.ACCEPTED,
                            JobStatus.QUEUED, JobStatus.RUNNING)
