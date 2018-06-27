try:
    from setuptools import setup, find_packages
except ImportError:
    import ez_setup
    ez_setup.use_setuptools()
    from setuptools import setup, find_packages


setup(
    name="Slivka",
    version="0.2.dev0",
    packages=find_packages(exclude=["tests", 'tests.*']),
    install_requires=[
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
    include_package_data=True,

    entry_points={
        "console_scripts": "slivka-setup=slivka.command:setup"
    },

    author="Mateusz Maciej Warowny",
    author_email="m.m.warowny@dundee.ac.uk",
    url="https://github.com/warownia1/Slivka",
    download_url="https://github.com/warownia1/Slivka/archive/master.zip",

    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Scientific/Engineering :: Bio-Informatics"
    ]
)
