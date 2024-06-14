======
Slivka
======

|version| |anaconda|

.. |version| image:: https://img.shields.io/badge/version-0.8.5b0-informational

.. |anaconda| image:: https://anaconda.org/slivka/slivka/badges/version.svg
   :target: https://anaconda.org/slivka/slivka

Slivka is a server application using Python 3.7+ intended for easy and flexible
creation of REST API for web services.
The server is based on Flask_ microframework and uses MongoDB_ as a backend storage.
Out intention is to create easily configurable and extensible interface for
running command line programs on a computer cluster.
Currently, `Univa Grid Engine`_ is supported out-of-the-box.
More information can be found in the documentation_.

.. _Flask: https://github.com/pallets/flask
.. _MongoDB: https://www.mongodb.com/
.. _`Univa Grid Engine`: http://www.univa.com/products/
.. _documentation: http://bartongroup.github.io/slivka/


------------
Installation
------------

Slivka is distributed as sources repository on GitHub_ and as a `conda package`_.

.. _GitHub: https://github.com/bartongroup/slivka
.. _conda package: https://anaconda.org/slivka/slivka

In order to install slivka from sources, clone the repository from GitHub::

  git clone https://github.com/bartongroup/slivka.git

navigate into the newly created directory and run the *setup.py* script
located in the repository's top directory with the Python interpreter.::

  python setup.py install

Installation with pip is also supported::

  python -m pip install <path to slivka>

or::

  python -m pip install git+https://github.com/bartongroup/slivka.git@master


Conda users may prefer to install slivka directly from our anaconda channel,
The package is provided by our *slivka* channel so make sure to
specify the channel name explicitly in the installation command.
We also recommend using *conda-forge* as a source for other dependencies.
You can either permanently append it to the channels list using ``conda config``
or tell conda to use it with additional ``-c conda-forge`` argument.
Keep in mind that development versions of slivka may not be available from
conda.::

  conda install -c slivka slivka

For Developers
==============

If you are the developer working with slivka sources, you may need to
install slivka in editable mode. It allows you make changes to the
installed package without the need to reinstall it every time.
Slivka can be installed in editable mode with either setuptools
(deprecated since python 3.10)::

  python setup.py develop

or using pip::

  python -m pip install -e <path to slivka>

For conda users, we recommend installing dependencies with conda first for the
slivka version you are going to work on::

  conda install --only-deps -c slivka slivka=<target-version>

and, after that, install slivka in editable mode without dependencies using pip::

  python -m pip install --no-deps -e <path to slivka>
