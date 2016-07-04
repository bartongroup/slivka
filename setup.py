try:
    from setuptools import setup
except ImportError:
    import ez_setup
    ez_setup.use_setuptools()
    from setuptools import setup


setup(
    name="PyBioAS",
    version="0.0.dev1",
    packages=["pybioas"],
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
        "console_scripts": "pybioas-setup=pybioas.command:setup"
    },

    author="Mateusz Maciej Warowny",
    author_email="m.m.warowny@dundee.ac.uk",
    url="https://github.com/warownia1/pyBioAS",
    download_url="https://github.com/warownia1/pyBioAS/archive/master.zip"
)
