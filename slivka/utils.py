import enum
import os
import re
import shutil

import jsonschema
import pkg_resources

try:
    import simplejson as json
except ImportError:
    import json

_FORM_SCHEMA_JSON = json.loads(
    pkg_resources.resource_string(
        "slivka",
        "data/config/FormDescriptionSchema.json"
    ).decode()
)
jsonschema.Draft4Validator.check_schema(_FORM_SCHEMA_JSON)
FORM_VALIDATOR = jsonschema.Draft4Validator(_FORM_SCHEMA_JSON)

_COMMAND_SCHEMA_JSON = json.loads(
    pkg_resources.resource_string(
        "slivka",
        "data/config/ConfDescriptionSchema.json"
    ).decode()
)
jsonschema.Draft4Validator.check_schema(_COMMAND_SCHEMA_JSON)
COMMAND_VALIDATOR = jsonschema.Draft4Validator(_COMMAND_SCHEMA_JSON)


class Singleton(type):
    __instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls.__instances:
            cls.__instances[cls] = super().__call__(*args, **kwargs)
        return cls.__instances[cls]


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
    n = 1
    obj = None
    while n < len(parts):
        try:
            obj = __import__('.'.join(parts[:-n]))
        except ImportError:
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


class JobStatus(enum.Enum):

    PENDING = 'pending'
    ACCEPTED = 'accepted'
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETED = 'completed'
    DELETED = 'deleted'
    FAILED = 'failed'
    ERROR = 'error'
    UNDEFINED = 'undefined'

    def is_finished(self):
        return self not in (JobStatus.PENDING, JobStatus.ACCEPTED,
                            JobStatus.QUEUED, JobStatus.RUNNING)
