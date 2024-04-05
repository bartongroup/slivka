import os
import sys

try:
    from setuptools import setup, find_packages
except ImportError:
    import ez_setup
    ez_setup.use_setuptools()
    from setuptools import setup, find_packages

about = {}

_about_file = os.path.join(os.path.dirname(__file__), 'slivka', '__about__.py')
exec(open(_about_file).read(), about)

setup(
    name="slivka",
    version=about['__version__'],
    packages=find_packages(exclude=["tests", 'tests.*']),
    install_requires= [
        "attrs>=19.0",
        "click>=7.0",
        "Flask>=2.0",
        "frozendict>=1.2",
        "jsonschema>=3.0",
        "MarkupSafe>=1.0",
        "packaging",
        "pymongo>=3.7",
        "python-daemon>=3.0",
        "PyYAML>=5.4",
        "pyzmq>=19.0",
        "simplejson>=3.16",
        "Werkzeug>=1.0",
    ],
    tests_require=[
        'mongomock>=3.18',
        'PyHamcrest>=2.0.4',
        'pytest-raises>=0.11',
        'pytest>=7.4',
        'sentinels>=1.0.0',
    ],
    extras_require={
        'gunicorn': ["gunicorn>=19.9"],
        'uwsgi': ['uWSGI>=2.0'],
        'bioinformatics': ['biopython>=1.72']
    },
    include_package_data=True,

    entry_points={
        "console_scripts": [
            "slivka=slivka.cli:main",
        ]
    },

    author="Mateusz Maciej Warowny",
    author_email="m.m.z.warowny@dundee.ac.uk",
    url="http://bartongroup.github.io/slivka/",
    download_url="https://github.com/bartongroup/slivka",

    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
        "Framework :: Flask",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: System :: Distributed Computing"
    ]
)
