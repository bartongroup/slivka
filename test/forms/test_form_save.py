from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from slivka.server.forms.file_proxy import FileProxy
from slivka.server.forms.form import *


class MyForm(BaseForm):
    _service = "test-example"

    ints_field = IntegerArrayField("ints", required=False)
    dec_field = DecimalField("dec", required=False)
    choice_field = ChoiceField(
        "choice", choices=[("a", "A"), ("b", "B"), ("c", "C")], required=False
    )
    flag_field = FlagField("flag", required=False)
    file_field = FileField("file", required=False)


def test_request_saved_to_database(database, tmp_path):
    form = MyForm(MultiDict())
    request_id = form.save(database, tmp_path).b64id
    job_request = JobRequest.find_one(database, id=request_id)
    assert job_request is not None


@pytest.mark.parametrize(
    "inputs, expected",
    [
        (
            [("ints", 19), ("ints", 20), ("ints", 21)],
            {"ints": ["19", "20", "21"]},
        ),
        ([("dec", 3.1415)], {"dec": "3.1415"}),
        ([("choice", "a"), ("ints", 0)], {"choice": "A", "ints": ["0"]}),
        ([("flag", "yes")], {"flag": "true"}),
        ([("flag", "no")], {}),
        pytest.param(
            [
                (
                    "file",
                    FileStorage(stream=BytesIO(b""), content_type="text/plain"),
                )
            ],
            {"file": ...},
            marks=pytest.mark.xfail(reason="file path is random"),
        ),
        (
            [("file", FileProxy(path="/tmp/pytest/file-path.txt"))],
            {"file": "/tmp/pytest/file-path.txt"},
        ),
    ],
)
def test_saved_inputs(database, tmp_path, inputs, expected):
    form = MyForm(MultiDict(inputs))
    request_id = form.save(database, tmp_path).b64id
    job_request = JobRequest.find_one(database, id=request_id)
    expected.setdefault("ints")
    expected.setdefault("dec")
    expected.setdefault("choice")
    expected.setdefault("flag")
    expected.setdefault("file")
    assert job_request.inputs == expected


def test_file_saved_to_file_system(database, tmp_path):
    fs = FileStorage(stream=BytesIO(b"text\n"), content_type="text/plain")
    form = MyForm(MultiDict([("file", fs)]))
    job_request = form.save(database, tmp_path)
    with open(job_request.inputs["file"], "rb") as f:
        assert f.read() == b"text\n"
