import logging
import os.path
from base64 import urlsafe_b64encode
from typing import Tuple, Iterable

import bson
import click
import pymongo.database
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from pymongo import MongoClient
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

name = "Nested job directory structure."
from_versions = SpecifierSet("<0.8.5b1", prereleases=True)
to_version = Version("0.8.5b1")


def apply(
        database: pymongo.database.Database,
        jobs_top_dir: str,
        skip_move_dirs: bool = False,
        skip_resolve_inputs: bool = False,
        skip_resolve_links: bool = False,
):
    requests_collection = database['requests']
    jobs_top_dir = os.path.normpath(jobs_top_dir)
    temp_symlinks = []
    if not skip_move_dirs:
        moved_dirs = move_job_directories(requests_collection, jobs_top_dir)
        for old, new in moved_dirs:
            os.symlink(new, old, target_is_directory=True)
            temp_symlinks.append(old)
    if not skip_resolve_inputs:
        normalize_file_inputs(requests_collection, jobs_top_dir)
    if not skip_resolve_links:
        resolve_symlinks(jobs_top_dir)
    for link in temp_symlinks:
        os.unlink(link)


def move_job_directories(requests_collection: pymongo.database.Collection, jobs_top_dir: str) -> Iterable[Tuple[str, str]]:
    """Moves job directories and updates the database accordingly.

    :return: list of old and new location pairs"""
    cursor_len = requests_collection.count_documents({"job.work_dir": {"$exists": True}})
    cursor = requests_collection.find({"job.work_dir": {"$exists": True}})
    logger.info("Moving %d jobs to new locations", cursor_len)
    for counter, request in enumerate(cursor, start=1):
        old_wd = request['job']['work_dir']
        req_id = request['_id']
        b64_req_id = urlsafe_b64encode(req_id.binary).decode()
        new_wd = make_job_path(jobs_top_dir, req_id)
        if old_wd == new_wd:
            logger.info("Identical source and target directories: %s", old_wd)
            continue
        try:
            logger.info(
                "Moving directory '%s' to '%s' (%d of %d)",
                old_wd, new_wd, counter, cursor_len
            )
            move_directory(old_wd, new_wd)
        except FileNotFoundError:
            logger.exception("File not found '%s'", old_wd)
            continue
        logger.info("Updating job record: %s", b64_req_id)
        requests_collection.update_one(
            {"_id": req_id},
            {"$set": {"job.work_dir": new_wd}}
        )
        logger.info("Job '%s' moved", b64_req_id)
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
    def _ensure_new_path_wrapper(val):
        if os.path.commonprefix([jobs_top_dir, val]) != jobs_top_dir:
            return val
        try:
            return ensure_new_style_path(val, jobs_top_dir)
        except ValueError:
            return val

    logger.info("Updating job inputs to new paths")
    for request in requests_collection.find():
        for name, value in request['inputs'].items():
            if value is None:
                continue
            if isinstance(value, str):
                new_value = _ensure_new_path_wrapper(value)
            elif isinstance(value, list):
                new_value = [_ensure_new_path_wrapper(v) for v in value]
            else:
                logger.warning("Parameter value is neither list or str: %r", value)
                continue
            if new_value == value:
                continue
            logger.info(
                "Changing 'inputs.%s' to %r from %r for job %s",
                name, new_value, value, urlsafe_b64encode(request['_id'].binary).decode()
            )
            requests_collection.update_one(
                {'_id': request['_id']},
                {'$set': {f'inputs.{name}': new_value}}
            )


def resolve_symlinks(top: str):
    """Update all symlinks under the `top` directory to point to their target directly"""
    logger.info("Fixing existing symlinks")
    top = os.path.abspath(top)
    all_files = (
        os.path.join(base, name)
        for job_dir in _iter_job_dirs(top)
        for base, dir_names, file_names in os.walk(job_dir)
        for name in dir_names + file_names
    )
    for link in filter(os.path.islink, all_files):
        # os.unlink followed by os.symlink causes race conditions
        target = os.readlink(link)
        if not os.path.isabs(target):
            logger.warning(f"The target of '%s' is relative: %s", link, target)
            continue
        if os.path.commonprefix([top, target]) != top:
            logger.debug("Skipping '%s': target outside the top dir: %s", link, target)
            continue
        new_target = ensure_new_style_path(target, top)
        if target == new_target:
            logger.debug("Link '%s' already fixed.", link)
            continue
        if not os.path.exists(new_target):
            logger.warning("New target does not exist: %s", new_target)
        temp_name = link + ".temp.symlink"
        logger.info("Resolving link %s", link)
        try:
            os.symlink(new_target, temp_name)
            os.replace(temp_name, link)
        except OSError:
            logger.exception("Failed to resolve '%s'", link)


def _iter_job_dirs(top: str) -> Iterable[os.DirEntry]:
    """Iterates all directories matching ??/??/????????????.

    This implementation is significantly faster than os.walk or glob.iglob
    as it does not collect entries or use expensive pattern matching.
    """
    for level1 in os.scandir(top):
        if not level1.is_dir(follow_symlinks=False) or len(level1.name) != 2:
            continue
        for level2 in os.scandir(level1):
            if not level2.is_dir(follow_symlinks=False) or len(level2.name) != 2:
                continue
            for level3 in os.scandir(level2):
                if not level3.is_dir(follow_symlinks=False) or len(level3.name) != 12:
                    continue
                yield level3



def ensure_new_style_path(path, top_dir):
    relative = os.path.relpath(path, top_dir)
    if relative.startswith('..'):
        raise ValueError(f"Path '{path}' is not relative to '{top_dir}'")
    (dir_name, remaining) = relative.split(os.sep, 1)
    if len(dir_name) != 16:
        # not an old style path
        return path
    return os.path.join(top_dir, dir_name[-2:], dir_name[-4:-2], dir_name[:-4], remaining)


@click.command(
    "1-nested-job-dirs",
    short_help=f"(ver. {to_version}) {name}"
)
@click.argument(
    "mongodb-uri",
    envvar=["SLIVKA_MONGODB_URI", "MONGODB_URI"],
    metavar="CONNECTION_STRING"
)
@click.argument(
    "database",
    envvar=["SLIVKA_MONGODB_DATABASE", "MONGODB_DATABASE"],
    metavar="DATABASE"
)
@click.option(
    "--slivka-home",
    envvar=["SLIVKA_HOME"],
    metavar="SLIVKA_HOME",
    help="Directory containing slivka config file.",
    show_default="current directory"
)
@click.option(
    "--jobs-dir",
    metavar="DIR",
    help="Specify jobs directory other than the default."
)
@click.option(
    "--skip-move-dirs",
    is_flag=True,
    hidden=True
)
@click.option(
    "--skip-resolve-inputs",
    is_flag=True,
    hidden=True
)
@click.option(
    "--skip-resolve-links",
    is_flag=True,
    hidden=True
)
def command(
        mongodb_uri,
        database,
        slivka_home,
        jobs_dir,
        skip_move_dirs,
        skip_resolve_inputs,
        skip_resolve_links,
):
    """Introduce two extra levels to jobs directory hierarchy.

    This migration reorganises job file directories to avoid a single
    directory with a massive number of subdirectories and updates the
    database entries accordingly. Instead of a single directory named
    after the jobs id, like `/jobs/12345678ABCD`, the new structure
    introduces two additional levels. The additional levels are named
    using the last four letters of the ID, two characters each, like
    `jobs/CD/AB/12345678`.

    Specify the mongodb server with CONNECTION_STRING and the database
    name with DATABASE arguments.
    """
    logging.basicConfig(level=logging.INFO)
    mongo = MongoClient(mongodb_uri)
    if jobs_dir is None:
        if slivka_home is None: slivka_home = os.getcwd()
        fnames = ['settings.yaml', 'settings.yml', 'config.yaml', 'config.yml']
        paths = (os.path.join(slivka_home, fn) for fn in fnames)
        try:
            config_path = next(filter(os.path.isfile, paths))
        except StopIteration:
            raise click.Abort(f"Configuration not found in {slivka_home}")
        yaml = YAML(typ="safe")
        config = yaml.load(open(config_path, 'r'))
        slivka_home = (
            config.get('directory.home') or
            config.get('directory', {}).get('home') or
            slivka_home
        )
        jobs_dir = (
            config.get('directory.jobs') or
            config.get('directory', {}).get('jobs')
        )
        jobs_dir = os.path.join(slivka_home, jobs_dir)
    apply(
        database=mongo[database],
        jobs_top_dir=jobs_dir,
        skip_move_dirs=skip_move_dirs,
        skip_resolve_inputs=skip_resolve_inputs,
        skip_resolve_links=skip_resolve_links
    )

if __name__ == '__main__':
    command()
