import json
import os
import re
import shutil

import pkg_resources

FORM_SCHEMA = json.loads(
    pkg_resources.resource_string(
        "slivka",
        "data/config/FormDescriptionSchema.json"
    ).decode()
)

CONF_SCHEMA = json.loads(
    pkg_resources.resource_string(
        "slivka",
        "data/config/ConfDescriptionSchema.json"
    ).decode()
)


class Singleton(type):
    __instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls.__instances:
            cls.__instances[cls] = super().__call__(*args, **kwargs)
        return cls.__instances[cls]


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
