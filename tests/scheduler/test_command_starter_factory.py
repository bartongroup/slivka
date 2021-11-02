import os.path

import yaml
from nose.tools import assert_equal, assert_list_equal, assert_is_instance, \
    assert_dict_equal

import slivka.conf.loaders
from scheduler.factory import runners_from_config
from utils import ConfigYamlLoader
from . import StubRunner

Argument = slivka.conf.loaders.ServiceConfig.Argument


class TestStarterFactory:
    def setup(self):
        fn = os.path.join(os.path.dirname(__file__), 'conf', 'service.yaml')
        conf = yaml.load(open(fn), ConfigYamlLoader)
        conf = slivka.conf.loaders.load_service_config("service", conf)
        selector, starter = runners_from_config(conf)
        self.starter = starter[0]

    def test_starter_name(self):
        assert_equal(self.starter.name, "default")

    def test_service_name(self):
        assert_equal(self.starter.service_name, "service")

    def test_base_command(self):
        assert_list_equal(self.starter.base_command, ["example.bin"])

    def test_arguments(self):
        expected = [
            Argument('option1', ['-o1', '$(value)']),
            Argument('option2', ['--option2=$(value)']),
            Argument('param1', ['-p1', '$(value)']),
            Argument('param2', ['$(value)'])
        ]
        assert_list_equal(self.starter.arguments, expected)

    def test_path_env(self):
        assert_equal(self.starter.env['PATH'], os.getenv('PATH'))

    def test_slivka_home_env(self):
        assert_equal(self.starter.env['SLIVKA_HOME'], os.getcwd())

    def test_custom_env(self):
        assert_equal(self.starter.env['EXAMPLE'], 'SENTINEL_VALUE')

    def test_runner_class(self):
        assert_is_instance(self.starter.runner, StubRunner)

    def test_runner_parameters(self):
        expected = {'stub_param1': "sentinel", 'stub_param2': 12}
        # noinspection PyUnresolvedReferences
        assert_dict_equal(self.starter.runner.init_kwargs, expected)
