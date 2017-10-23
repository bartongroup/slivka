"""Main execution script for the module.

This module makes slivka project executable. It's sole purpose is to execute
the setup function which will initialize a new project in the working
directory where the module was launched.
"""

import slivka.command

if __name__ == "__main__":
    slivka.command.setup()
