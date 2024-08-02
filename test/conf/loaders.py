import os
from unittest import mock

import pytest
import yaml

import slivka.conf.loaders
from slivka.compat.resources import open_text


@pytest.fixture
def dict_config():
    with open_text('test', 'resources/minimal_project/settings.yaml') as stream:
        return yaml.safe_load(stream)


def test_conf_directory_real_path(tmp_path, dict_config):
    real_home = tmp_path / "real-slivka"
    os.mkdir(real_home)
    home = tmp_path / "slivka"
    os.symlink(real_home, home, target_is_directory=True)
    with mock.patch.dict(os.environ, SLIVKA_HOME=str(home)):
        conf = slivka.conf.loaders.load_settings_0_3(dict_config)
    assert conf.directory.home == str(real_home)
    assert conf.directory.jobs == str(real_home / 'jobs')
    assert conf.directory.uploads == str(real_home / 'uploads')
    assert conf.directory.logs == str(real_home / 'log')
    assert conf.directory.services == str(real_home)
