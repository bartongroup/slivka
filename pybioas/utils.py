import json
import os
import re
import shutil

import pkg_resources

COMMAND_SCHEMA = json.loads(
    pkg_resources.resource_string(
        "pybioas",
        "data/utils/CommandDescriptionSchema.json"
    ).decode()
)


def copytree(src, dst):
    """
    Alternative implementation of shutil.copytree which allows to copy into
    existing directories.
    :param src:
    :param dst:
    :return:
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
    """
    Converts snake_case name to lowercase camelCase
    :param name: name to convert
    :return: camelCase name
    """
    comp = name.split('_')
    return comp[0] + ''.join(map(str.capitalize, comp[1:]))


def camel_to_snake(name):
    """
    Converts camelCase name to snake_case
    :param name: name to convert
    :return: snake_case name
    """
    s = re.sub('([A-Z])([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s).lower()
