import enum
import os
import re
import shutil
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


# ## Path and file traversal utilities ##

def locate(path):
    """Imports any module or object accessible from the PYTHONPATH.

    Improved implementation of the __import__ function that can fetch
    members and attributes in addition to the modules.

    :param path: dot separated path to the object
    :return: object
    :raises ModuleNotFoundError: if the module is not found
    :raises AttributeError: if the object attribute is missing
    """
    parts = path.split('.')
    n = 0
    obj = None
    while n < len(parts):
        import_path = '.'.join(parts[:len(parts)-n])
        try:
            obj = __import__(import_path)
        except ImportError as e:
            if e.name != import_path:
                raise
            n += 1
        else:
            break
    if obj is None:
        raise ImportError('No module named \'%s\'' % parts[0])
    for part in parts[1:]:
        obj = getattr(obj, part)
    return obj


def copytree(src, dst):
    """Copy directory tree recursively.
    
    Alternative implementation of shutil.copytree which allows to copy into
    existing directories. Directories which does not exist are created and
    existing directories are populated with files and folders.
    If destination directory path does not exist, it will attempt to create
    the entire directory tree up to that level.
    
    :param src: source directory path
    :param dst: destination directory path
    :return: destination directory path
    """
    os.makedirs(dst, exist_ok=True)
    errors = []
    for name in os.listdir(src):
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if os.path.isdir(srcname):
                copytree(srcname, dstname)
            else:
                shutil.copy(srcname, dstname)
        except shutil.Error as err:
            errors.extend(err.args[0])
        except OSError as err:
            errors.append((srcname, dstname, str(err)))
    if errors:
        raise shutil.Error(errors)
    return dst


def recursive_scandir(path='.'):
    """Returns an iterator of ``os.DirEntry`` of files in the directory."""
    for entry in os.scandir(path):
        if entry.is_dir():
            yield from recursive_scandir(entry.path)
        else:
            yield entry


def snake_to_camel(name):
    """Convert snake_case name to lowercase camelCase
    
    :param name: snake_case name
    :return: camelCase name
    """
    comp = name.split('_')
    return comp[0] + ''.join(map(str.capitalize, comp[1:]))


def camel_to_snake(name):
    """Convert camelCase name to snake_case
    
    :param name: camelCase name
    :return: snake_case name
    """
    s = re.sub('([A-Z])([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s).lower()


class JobStatus(enum.IntEnum):
    PENDING = 1
    REJECTED = 2
    ACCEPTED = 3
    QUEUED = 4
    RUNNING = 5
    COMPLETED = 6
    INTERRUPTED = 7
    DELETED = 8
    FAILED = 9
    ERROR = 10
    UNDEFINED = 11

    def is_finished(self):
        return self not in (JobStatus.PENDING, JobStatus.ACCEPTED,
                            JobStatus.QUEUED, JobStatus.RUNNING)
