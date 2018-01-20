============
Requirements
============

Installation requires Python 3.3+ (recommended version 3.5).
Additional requirements, which will be downloaded and installed automatically,
are:

- click (6.6)
- Flask (0.11.1)
- itsdangerous (0.24)
- Jinja2 (2.8)
- jsonschema (2.5.1)
- MarkupSafe (0.23)
- PyYAML (3.11)
- SQLAlchemy (1.0.13)
- Werkzeug (0.11.10)

============
Installation
============

It's recommended to install Slivka inside a virtual environment.
Get virtualenv with ``pip install virtualenv`` (on some Linux distributions
you may need to install ``apt-get install python-virtualenv``).
Run ``virtualenv env``, wait for it to create a new environment in ``env``
directory and activate using ``source env/bin/activate`` on Unix/OS X or
``env\Scripts\activate.bat`` on Windows. More information about the package
can be found in `virtualenv documentation`_.

.. _`virtualenv documentation`: https://virtualenv.pypa.io/en/stable/

To install Slivka download Slivka zip or tar archive form here_ and run
``pip install Slivka-<version>.(zip|tar)`` on the downloaded file.
Alternatively, you can install the most recent version directly from the github
repository with ``pip install git+git://github.com/warownia1/Slivka``.
Setuptools and all requirements will be downloaded if not present, so internet
connection is required during the installation.

.. _here: https://github.com/warownia1/Slivka/releases

Installation will create a new executable ``slivka-setup`` in your Python
scripts directory. It can be used to initialize new projects.
