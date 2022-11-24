************
Installation
************

==============
Python Version
==============

Slivka supports Python 3.7 and above and was developed and tested on
that version of Python. However, we recommend using the latest version
of Python and reporting any compatibility issues on `our GitHub`_
issue tracker.

.. _`our GitHub`: https://github.com/bartongroup/slivka/issues

============
Dependencies
============

All required dependencies will be installed automatically when
installing slivka. Those include, but are not limited to:

- Flask_ is a WSGI web framework used to create REST endpoints for
  the web services
- PyYAML_ is a Python implementation of the YAML parser and serializer
- click_ provides a command line interface for slivka
- pymongo_ contains tools for working with a `Mongo database`_ from Python
- pyzmq_ provides Python bindings for ØMQ_
- attrs_ provides lightweight class-based data containers

.. _Flask: https://flask.palletsprojects.com
.. _PyYAML: https://pyyaml.org/
.. _click: https://click.palletsprojects.com
.. _pymongo: https://pymongo.readthedocs.io
.. _`Mongo database`: https://www.mongodb.com/
.. _pyzmq: https://pyzmq.readthedocs.io
.. _ØMQ: https://zeromq.org/
.. _attrs: https://www.attrs.org

=====================
Optional Dependencies
=====================

Those packages are not installed automatically, but slivka can detect
them extending its functionality when present.

- Gunicorn_ is a fairly fast and lightweight WSGI HTTP Server for UNIX
  which we recommend using as an application server
- uWSGI_ aims for developing a full stack for building hosting
  services, the project is in maintenance mode since April 2022, a
  common alternative to Gunicorn
- Biopython_ is a collection of tools for biological computation, it
  allows slivka to recognise bioinformatic file types

.. _Biopython: https://biopython.org/
.. _Gunicorn: https://gunicorn.org/
.. _uWSGI: http://projects.unbit.it/uwsgi

==============
Mongo Database
==============

Make sure a Mongo database is installed and running on your system
before proceeding as slivka requires it for proper operation. If you
do not have MongoDB running on your system you can install is locally
using conda or ask your system administrator to install and configure
it system-wide.

.. code::

  conda install -c conda-forge mongodb

============================
Installing slivka with conda
============================

A recommended way to install slivka is by using the conda package
manager. Slivka package is accessible from the slivka channel on
`anaconda.org`_. Make sure that the command line tools you intend to
expose as web services are executable from where the slivka is
installed (machine or VM). They do not need to be installed in the
same conda environment though. Create a new environment substituting
an environment name for ``<env>`` activate it and install slivka and
its dependencies from slivka and conda-forge channels.

.. _`anaconda.org`: https://anaconda.org/slivka/slivka

.. code::

  conda create -n <env> python
  conda activate <env>
  conda install -c slivka -c conda-forge slivka

==============================
Installing slivka from sources
==============================

If you are a developer wanting to develop slivka package or you do not
want to depend on conda then you should consider installing slivka
from sources.

Either clone out git repository ``https://github.com/bartongroup/slivka.git``
or download and extract the zip archive containing the sources here__.
Next, navigate to the package root directory (the one containing
the *setup.py* script) and run ::

  python setup.py install

.. __: https://github.com/bartongroup/slivka/archive/master.zip

You can alternatively use pip to automatically fetch and install the
package from the GitHub repository ::

  pip install git+git://github.com/bartongroup/slivka.git

Slivka is now installed. You can verify if it was installed
correctly by executing the ``slivka`` command e.g. displaying the
current software version

.. code::

  slivka --version
