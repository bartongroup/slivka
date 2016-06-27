import json
import os.path
import sys

from settings import BASE_DIR


command_description_schema_path = os.path.join(
    BASE_DIR, "utils", "CommandDescriptionSchema.json")
try:
    with open(command_description_schema_path, "r") as schema_file:
        COMMAND_SCHEMA = json.load(schema_file)
except FileNotFoundError:
    print("CommandDescriptionSchema.json not found", file=sys.stderr)
    COMMAND_SCHEMA = {}
except json.JSONDecodeError as err:
    print(err.msg, file=sys.stderr)
    COMMAND_SCHEMA = {}
