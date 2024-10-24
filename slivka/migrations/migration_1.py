import os.path
import pathlib

import ruamel.yaml
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from slivka.utils.path import request_id_to_job_path

name = "Nested job directory structure"
from_versions = SpecifierSet("<=0.8.4", prereleases=True)
to_version = Version("0.8.5")


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
        settings["version"] = "0.8.5"
        with open(slivka.conf.settings.settings_file, "w") as f:
            yaml.dump(settings, f)
