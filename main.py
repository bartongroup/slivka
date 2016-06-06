#!usr/bin/env

import argparse
import json
import os.path
from configparser import ConfigParser

from command import CommandRunnerFactory


ROOT_DIR = os.path.dirname(__file__)
SERVICE = "Dummy"


class Main(object):

    def __init__(self):
        cfg = ConfigParser()
        cfg.read("./config/services.ini")
        services = cfg.sections()
        self.service_runner_factory = {}
        for service in services:
            params_path = os.path.join(ROOT_DIR, cfg.get(service, "parameters"))
            bin_path = os.path.join(ROOT_DIR, cfg.get(service, "bin"))
            env = {
                param[4:]: value
                for param, value in cfg.items(service)
                if param[:3] == "env"
            }
            self.service_runner_factory[service] = \
                CommandRunnerFactory(bin_path, params_path, env or None)

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-i", "--input")
        args = parser.parse_args()

        if args.input is None:
            print("no input file, saving to %sOptions.json" % SERVICE)
            options = self.service_runner_factory[SERVICE].options
            save_json(options, "%sOptions.json" % SERVICE)
        else:
            values = get_values_from_json(args.input)
            runner = self.service_runner_factory[SERVICE].get_command_runner()
            runner.set_values(values)
            res = runner.run_command()
            print(res)


def get_values_from_json(path):
    with open(path, "r") as f:
        obj = json.load(f)
    return {opt_id: o['value'] for (opt_id, o) in obj.items()}


def save_json(options, path):
    obj = {
        option.id: {
            "name": option.name,
            "value": option.default
        }
        for option in options
    }
    with open(path, "w") as f:
        json.dump(obj, f, indent=4)


if __name__ == "__main__":
    main = Main()
    main.main()
