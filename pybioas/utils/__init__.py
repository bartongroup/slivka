import json
import os
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
