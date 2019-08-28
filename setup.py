import os

try:
    from setuptools import setup, find_packages
except ImportError:
    import ez_setup
    ez_setup.use_setuptools()
    from setuptools import setup, find_packages

about = {}

with open(os.path.join(
        os.path.dirname(__file__), 'slivka', '__about__.py')) as f:
    exec(f.read(), about)

setup(
    name="Slivka",
    version=about['__version__'],
    packages=find_packages(exclude=["tests", 'tests.*']),
    install_requires=[
        "click>=6.6",
        "Flask>=0.11.1",
        "frozendict>=1.2",
        "itsdangerous>=0.24",
        "Jinja2>=2.8",
        "jsonschema>=2.5.1",
        "MarkupSafe>=0.23",
        "PyYAML>=3.11",
        "simplejson>=3.16.0",
        "SQLAlchemy>=1.0.13",
        'typing>=3.6;python_version<"3.5"',
        "Werkzeug>=0.11.10",
    ],
    extras_require={
        'bioinformatics': ['biopython>=1.72']
    },
    include_package_data=True,

    entry_points={
        "console_scripts": [
            "slivka-setup=slivka.command:setup",
            "slivka-queue=slivka.local_queue:main"
        ]
    },

    author="Mateusz Maciej Warowny",
    author_email="m.m.warowny@dundee.ac.uk",
    url="https://github.com/warownia1/Slivka",
    download_url="https://github.com/warownia1/Slivka/archive/master.zip",

    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Scientific/Engineering :: Bio-Informatics"
    ]
)
