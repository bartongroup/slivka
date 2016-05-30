#!usr/bin/env

import argparse
import json
import os.path

from command_runner import CommandRunner


def main():
    path = os.path.join('config', "MuscleParameters.xml")
    runner = CommandRunner(path)

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input")
    args = parser.parse_args()

    if args.input is None:
        print("no input file, saving to MuscleOptions.json")
        options = runner.get_options()
        save_json(options, "MuscleOptions.json")
    else:
        values = get_values_from_json(args.input)
        runner.set_values(values)
        print(runner.build_command())


def get_values_from_json(path):
    with open(path, "r") as f:
        obj = json.load(f)
    return {id: o['value'] for (id, o) in obj.items()}


def save_json(options, path):
    obj = {
        option.id: {
            "name": option.name,
            "value": option.default_value
        }
        for option in options
    }
    with open(path, "w") as f:
        json.dump(obj, f, indent=4)


if __name__ == "__main__":
    main()
