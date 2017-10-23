import configparser
import os
import sys

from .exceptions import ValidationError
from .form_factory import FormFactory


def init_forms(config_file):
    """Initialize ``forms`` module.

    Load services and their parameter files from configuration and
    dynamically creates corresponding form classes. The classes are dynamically
    added to the forms module.

    :param config_file:
    """
    config = configparser.ConfigParser()
    with open(config_file, 'r') as f:
        config.read_file(f)
    module = sys.modules[__name__]
    for service in config.sections():
        form_name = get_form_name(service)
        form_file = os.path.normpath(config.get(service, "form"))
        form_class = \
            FormFactory.get_form_class(form_name, service, form_file)
        setattr(module, form_name, form_class)


def get_form(service):
    """Get the form bound to the specified service.

    :param service: name of the service
    :return: form associated with a given service
    """
    module = sys.modules[__name__]
    return getattr(module, get_form_name(service))


def get_form_name(service):
    """Generate form class name from service name.

    :param service: service name
    :return: form name for the given service
    """
    return service.capitalize() + "Form"
