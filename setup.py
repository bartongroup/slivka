import os

import ez_setup

ez_setup.use_setuptools()

from setuptools import setup


setup(
    name="PyBioAS",
    version="0.0.dev1",
    packages=["pybioas"],
    setup_requires=[
        "click==6.6",
        "Flask==0.11.1",
        "itsdangerous==0.24",
        "Jinja2==2.8",
        "jsonschema==2.5.1",
        "MarkupSafe==0.23",
        "PyYAML==3.11",
        "SQLAlchemy==1.0.13",
        "Werkzeug==0.11.10",
    ],
    package_data={
        "pybioas": [
            os.path.relpath(os.path.join(dirpath, filename), "pybioas")
            for (dirpath, dirnames, filenames)
            in os.walk(os.path.join('pybioas', 'data'))
            for filename in filenames
        ]
    },
    entry_points={
        "console_scripts": "pybioas=pybioas:main"
    }
)
