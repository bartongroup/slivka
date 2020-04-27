#!/usr/bin/env python3

import os
import sys

home = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    home = os.environ.get('SLIVKA_HOME', home)
    os.environ.setdefault('SLIVKA_HOME', home)
    sys.path.append(home)
    try:
        import slivka.cli
    except ImportError:
        raise ImportError(
            "Couldn't import slivka. Make sure it's installed corectly "
            "and available from PYTHONPATH environment variable. "
            "Check if you activated virtual environment."
        )
    slivka.cli.main()
