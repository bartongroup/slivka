#!usr/bin/env

import argparse
import json
import os.path

from lxml import etree


class CommandOption(object):

    def __init__(self, option_element):
        self.id = option_element.get("id")
        self.required = option_element.get("required", False)
        self.name = option_element.find("name").text
        self.param = option_element.find("param").text
        value = option_element.find("value")
        self.value_type = value.find("type").text
        default = value.find("default")
        self.default_value = default.text if default is not None else None
        self.value = None

    def __repr__(self):
        if self.value is None:
            return "{name} : {type}".format(name=self.name, type=self.value_type)
        else:
            return "{name}={value}".format(name=self.name, value=self.value)

    def set_value(self, value):
        self.value = value


    @staticmethod
    def load_from_param_file(service):
        filename = "{0}Parameters.xml".format(service)
        path = os.path.join('config', filename)
        parser = etree.XMLParser(remove_blank_text=True)
        runner_config = etree.parse(path, parser=parser).getroot()
        options = [CommandOption(option) for option in runner_config]
        return options


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input")
    args = parser.parse_args()

    options = CommandOption.load_from_param_file("Muscle")

    if args.input is None:
        save_json(options, "MuscleOptions.json")
    else:
        fill_values_from_json(options, args.input)
        args = build_command(options)
        print(" ".join(args))


def fill_values_from_json(options, path):
    with open(path, "r") as f:
        obj = json.load(f)
    for option in options:
        option.set_value(obj.get(option.id)['value'])


def save_json(options, path):
    res = dict()
    obj = {
        option.id: {
            "name": option.name,
            "value": option.default_value
        }
        for option in options
    }
    with open(path, "w") as f:
        json.dump(obj, f, indent=4)


def build_command(options):
    args = []
    for option in options:
        if option.value is not None:
            args.extend([option.param, option.value])
    return args


if __name__ == "__main__":
    main()
