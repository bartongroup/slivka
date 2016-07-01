import json
import os.path

import pybioas.settings

command_description_schema_path = os.path.join(
    pybioas.settings.BASE_DIR,
    "data", "utils", "CommandDescriptionSchema.json"
)
with open(command_description_schema_path, "r") as schema_file:
    COMMAND_SCHEMA = json.load(schema_file)
