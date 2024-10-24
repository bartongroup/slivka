import os
import pathlib

from typing import Union

__all__ = [
    "request_id_to_job_path",
    "job_file_path_to_file_id"
]



def request_id_to_job_path(base_path, b64id):
    """
    Builds a path to the work directory from the request
    identifier.

    :param base_path: path to the jobs directory
    :param b64id: base64 encoded request id
    :return: path to the job work directory
    """
    assert len(b64id) == 16
    return os.path.join(base_path, b64id[-2:], b64id[-4:-2], b64id[:-4])


def job_file_path_to_file_id(base_path: str, path: Union[str, pathlib.Path]):
    """
    Converts absolute file path to the file id consisting of
    the job id which generated the file and the relative path
    to the file.

    FIXME: This method exists to circumvent the problem of converting
        input file paths back to identifiers when displaying
        job input parameters to the clients.

    :param base_path: path to the jobs directory
    :param path: absolute path to the file
    :return: file id <job id>/<relative path>
    """
    rel_path = pathlib.Path(path).relative_to(base_path)
    parts = iter(rel_path.parts)
    job_id = ''
    while len(job_id) < 16:
        job_id = next(parts) + job_id
    if len(job_id) != 16:
        raise ValueError(f"Path {base_path} could not be converted.")
    return f"{job_id}/{str.join('/', parts)}"
