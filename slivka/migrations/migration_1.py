import os.path
import sys
from base64 import urlsafe_b64encode
from typing import List, Tuple, Iterable

import bson
import pymongo.database
from packaging.specifiers import SpecifierSet
from packaging.version import Version

name = "Nested job directory structure"
from_versions = SpecifierSet("<0.8.5b1", prereleases=True)
to_version = Version("0.8.5b1")


def apply(database: pymongo.database.Database, jobs_top_dir: str):
    requests_collection = database['requests']
    moved_dirs = move_job_directories(requests_collection, jobs_top_dir)
    temp_symlinks = []
    for old, new in moved_dirs:
        os.symlink(new, old, target_is_directory=True)
        temp_symlinks.append(old)
    normalize_file_inputs(requests_collection, jobs_top_dir)
    normalize_symlinks(jobs_top_dir)
    for link in temp_symlinks:
        os.unlink(link)


def move_job_directories(requests_collection: pymongo.database.Collection, jobs_top_dir: str) -> Iterable[Tuple[str, str]]:
    """Moves job directories and updates the database accordingly.

    :return: list of old and new location pairs"""
    for request in requests_collection.find({"job.work_dir": {"$exists": True}}):
        old_wd = request['job']['work_dir']
        new_wd = make_job_path(jobs_top_dir, request['_id'])
        try:
            move_directory(old_wd, new_wd)
        except FileNotFoundError:
            print(f"File not found: {old_wd}", file=sys.stderr)
            continue
        requests_collection.update_one(
            {"_id": request['_id']},
            {"$set": {"job.work_dir": new_wd}}
        )
        yield old_wd, new_wd


def move_directory(old_wd: str, new_wd: str):
    """Moves directory tree to a new location?"""
    if not os.path.isdir(old_wd):
        raise FileNotFoundError(str(old_wd))
    os.makedirs(new_wd)
    os.replace(old_wd, new_wd)


def make_job_path(base_path, object_id: bson.ObjectId) -> str:
    """Creates a new job path from the object id"""
    b64id = urlsafe_b64encode(object_id.binary).decode()
    return os.path.abspath(
        os.path.join(base_path, b64id[-2:], b64id[-4:-2], b64id[:-4])
    )


def normalize_file_inputs(requests_collection: pymongo.database.Collection, jobs_top_dir: str):
    """
    Changes all inputs in the collection that are paths under the
    `jobs_top_dir` to point to their real locations.
    """
    for request in requests_collection.find():
        for name, value in request['inputs'].items():
            if not value.startswith(jobs_top_dir):
                continue
            new_value = os.path.realpath(value)
            if new_value == value:
                continue
            requests_collection.update_one(
                {'_id': request['_id']},
                {'$set': {f'inputs.{name}': new_value}}
            )


def normalize_symlinks(top: str):
    """Update all symlinks under the `top` directory to point to their target directly"""
    top = os.path.abspath(top)
    all_files = (
        os.path.join(base, fn)
        for base, _dirnames, filenames in os.walk(top)
        for fn in filenames
    )
    for link in filter(os.path.islink, all_files):
        # os.unlink followed by os.symlink causes race conditions
        temp_name = link + ".temp.symlink"
        os.symlink(os.path.realpath(link), temp_name)
        os.replace(temp_name, link)

