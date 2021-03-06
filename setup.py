import os

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
    name="Slivka",
    version=about['__version__'],
    packages=find_packages(exclude=["tests", 'tests.*']),
    install_requires=[
        "attrs>=19",
        "click>=7.0",
        "Flask>=1.0",
        "frozendict>=1.2",
        "jsonschema>=2.5.1",
        "MarkupSafe>=1.0",
        "pymongo>=3.7",
        "PyYAML>=3.11",
        "pyzmq>=17.0"
        "simplejson>=3.16.0",
        "Werkzeug>=0.15",
    ],
    tests_require=[
        'nose>=1.3.7',
        'mongomock>=3.18.0'
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
    url="https://github.com/warownia1/Slivka",
    download_url="https://github.com/warownia1/Slivka/archive/dev.zip",

    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3 :: Only",
        "Framework :: Flask",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: System :: Distributed Computing"
    ]
)
