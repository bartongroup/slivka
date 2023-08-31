import contextlib
import os

import pytest
from sentinels import Sentinel
from werkzeug.datastructures import MultiDict, FileStorage

from slivka.db.documents import UploadedFile
from slivka.db.helpers import insert_one, delete_one
from slivka.server.forms.fields import FileField, ValidationError, FileArrayField

data_dir_path = os.path.join(os.path.dirname(__file__), "data")


@pytest.fixture()
def plain_text_file(database):
    uploaded_file = UploadedFile(
        title="example-file",
        media_type="text/plain",
        path=os.path.join(data_dir_path, "lipsum.txt"),
    )
    insert_one(database, uploaded_file)
    yield uploaded_file
    delete_one(database, uploaded_file)


def test_fetch_value_file_from_multipart():
    field = FileField("test1")
    data = MultiDict()
    files = MultiDict({"test1": Sentinel("FILE")})
    assert field.fetch_value(data, files) == Sentinel("FILE")


def test_fetch_value_id_from_data():
    field = FileField("test1")
    data = MultiDict({"test1": "deadbeef"})
    files = MultiDict()
    assert field.fetch_value(data, files) == "deadbeef"


def test_fetch_value_ids_from_data_first_value_returned():
    field = FileField("test1")
    data = MultiDict([("test1", "c0ffee"), ("test1", "f00b4r")])
    files = MultiDict()
    assert field.fetch_value(data, files) == "c0ffee"


def test_fetch_value_mixed_data_and_multipart_first_file_returned():
    field = FileField("test1")
    data = MultiDict([("test1", "c0ffee"), ("test1", "f00b4r")])
    files = MultiDict([("test1", Sentinel("FILE"))])
    assert field.fetch_value(data, files) == Sentinel("FILE")


def test_array_fetch_value_ids_from_data_all_values_returned():
    field = FileArrayField("test1")
    data = MultiDict([("test1", "c0ffee"), ("test1", "f00b4r")])
    files = MultiDict()
    assert field.fetch_value(data, files) == ["c0ffee", "f00b4r"]


def test_validate_uploaded_file_id_converted_to_file(plain_text_file):
    field = FileField("test1")
    file = field.validate(plain_text_file.b64id)
    with contextlib.closing(file) as stream:
        assert stream.readline() == b"Lorem ipsum dolor sit amet\n"


def test_validate_missing_file_id_validation_error_raised(database):
    field = FileField("test1")
    with pytest.raises(ValidationError) as exc_info:
        field.validate("1Ddoe5N0t3xist__")
    assert exc_info.value.code == "not_found"


def test_validate_file_from_post_data(database):
    field = FileField("test")
    path = os.path.join(os.path.dirname(__file__), "data", "lipsum.txt")
    fs = FileStorage(
        stream=open(path, "rb"), filename="lipsum.txt", name="test"
    )
    file = field.validate(fs)
    with contextlib.closing(file) as stream:
        assert stream.readline() == b"Lorem ipsum dolor sit amet\n"


@pytest.mark.parametrize(
    "media_type, basename",
    [
        pytest.param("text/plain", "lipsum.txt"),
        pytest.param("text/plain", "example.json"),
        pytest.param(
            "text/plain",
            "example.bin",
            marks=pytest.mark.raises(exception=ValidationError),
        ),
        pytest.param("application/json", "example.json"),
        pytest.param(
            "application/json",
            "lipsum.txt",
            marks=pytest.mark.raises(excepiton=ValidationError),
        ),
        pytest.param(
            "application/json",
            "example.bin",
            marks=pytest.mark.raises(exception=ValidationError),
        ),
        pytest.param("application/octet-stream", "example.bin"),
        pytest.param("application/octet-stream", "lipsum.txt"),
    ],
)
def test_validate_media_type(media_type: str, basename: str):
    field = FileField("test1", media_type=media_type)
    path = os.path.join(data_dir_path, basename)
    fs = FileStorage(
        stream=open(path, "rb"), filename=basename, name="test_file"
    )
    field.validate(fs)
