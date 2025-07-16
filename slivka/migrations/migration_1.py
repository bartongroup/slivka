import os.path
import sys
from base64 import urlsafe_b64encode
from pathlib import Path
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
        os.symlink(new, old)
        temp_symlinks.append(old)
    normalize_file_inputs(requests_collection, jobs_top_dir)
    normalize_symlinks(jobs_top_dir)
    for link in temp_symlinks:
        os.unlink(link)


def move_job_directories(requests_collection: pymongo.database.Collection, jobs_top_dir: str) -> Iterable[Tuple[Path, Path]]:
    """Moves job directories and updates the database accordingly.

    :return: list of old and new location pairs"""
    for request in requests_collection.find({"job.work_dir": {"$exists": True}}):
        old_wd = Path(request['job']['work_dir'])
        new_wd = make_job_path(jobs_top_dir, request['_id'])
        try:
            new_wd = move_directory(old_wd, new_wd)
        except FileNotFoundError:
            print(f"File not found: {old_wd}", file=sys.stderr)
            continue
        old_wd.symlink_to(new_wd, target_is_directory=True)
        requests_collection.update_one(
            {"_id": request['_id']},
            {"$set": {"job.work_dir": new_wd}}
        )
        yield old_wd, new_wd


def move_directory(old_wd: Path, new_wd: str):
    """Moves directory tree to a new location?"""
    if not old_wd.is_dir():
        raise FileNotFoundError(str(old_wd))
    os.makedirs(new_wd)
    return old_wd.replace(new_wd)


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
        for name, value in request['inputs']:
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


def apply():
    import slivka.db
    import slivka.db.documents
    import slivka.conf
    import slivka.scheduler.scheduler
    requests_collection = slivka.db.database['requests']
    jobs_directory = slivka.conf.settings.directory.jobs
    for request in requests_collection.find():
        request = slivka.db.documents.JobRequest(**request)
        old_wd = pathlib.Path(request.job.work_dir)
        if not old_wd.is_dir():
            print(f"Missing directory of job {request.b64id}. Skipping.")
            continue
        new_wd = os.path.abspath(
            request_id_to_job_path(jobs_directory, request.b64id)
        )
        requests_collection.update_one(
            {"_id": request['_id']},
            {"$set": {"job.work_dir": new_wd}}
        )
        os.makedirs(new_wd)
        old_wd.replace(new_wd)
    if slivka.conf.settings.settings_file:
        yaml = ruamel.yaml.YAML()
        with open(slivka.conf.settings.settings_file) as f:
            settings = yaml.load(f)
        settings["version"] = "0.8.5b1"
        with open(slivka.conf.settings.settings_file, "w") as f:
            yaml.dump(settings, f)
