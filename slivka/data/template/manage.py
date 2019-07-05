#!/usr/bin/env python3

import os

SETTINGS_FILE = 'settings.yml'


if __name__ == "__main__":
    settings_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), SETTINGS_FILE
    )
    os.environ.setdefault('SLIVKA_SETTINGS', settings_path)
    try:
        import slivka.command
    except ImportError:
        raise ImportError(
            "Couldn't import slivka. Make sure it's installed corectly "
            "and available on you PYTHONPATH environment variable. "
            "Check if you activated virtual environment."
        )
    slivka.command.manager()
