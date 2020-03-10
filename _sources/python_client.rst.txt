===================
Client applications
===================

--------
REST API
--------

Slivka provides REST API which allows you to develop applications that interact with
the servers. The interactive view of available API endpoints is available at ``api/``
endpoint of every Slivka server.

------
Python
------

If you are using Python, there is an official Slivka client library that abstracts
communication with the server. The most recent version of the library can be installed
from our github repository::

    pip install git+https://github.com/warownia1/slivka-python-client.git

Usage
=====

Creating client
---------------

Once the library is installed, you can import :class:`.SlivkaClient` form :mod:`slivka_client`
module and create client instance using a single *url* argument or provide
*scheme*, *auth*, *host*, *port* and *path* as individual keyword arguments.

.. warning::
    Remember to add trailing slash at the end of the path.
    ``example.org/slivka`` means ``slivka`` resource under ``/`` path,
    while ``example.org/slivka/`` indicates resources under ``/slivka/`` path.

.. code-block:: python

    >>> from slivka_client import SlivkaClient

    >>> client = SlivkaClient('http://example.org/slivka/')
    >>> # or SlivkaClient(schema='http', host='example.org', path='slivka/')
    >>> client.url
    Url(scheme='http', auth=None, host='example.org',
        port=None, path='/slivka/', query=None, fragment=None)


:class:`slivka_client.SlivkaClient` is the starting point to services discovery,
file upload and retrieval and job monitoring.

Services listing and job submission
-----------------------------------

The list of services can be accessed through :attr:`services` property.
The server will be contacted to provide the list of services on the first property access.
Subsequent attempts will return the cached list immediately. Use :meth:`refresh_services`
method whenever you want to reload the list of services from the server.

.. code-block:: python

    >>> client.services
    [SlivkaService(example_one), SlivkaService(example_two)]
    >>> service = client.services[0]
    >>> service.name
    'example_one'
    >>> service.form
    Form(example_one)

Service object represents a single service on the server side and its :attr:`~.Service.form`
property creates a new submission form needed to run jobs.
A new empty form is created every time the property is accessed.
Alternatively, if you prefer more explicit approach, you can call :meth:`.Service.new_form`
method which returns a new form.

Forms are dict-like iterable objects providing a view of the service input parameters,
serving as a containers for the input data and handling job submissions.
Iterating over the form yields field description objects with properties
according to the their type. The properties common for all field types are:

:type: type of the field (see :class:`~slivka_client.FieldType`)
:name: field name/identifier
:label: short human-readable label
:description: longer, more detailed description
:required: whether the field is required or not
:default: default value or ``None`` if not provided
:multiple: whether multiple values are accepted

The available properties of each form field are described in the API Reference
section `Form Fields`_.

The list of fields can be accessed through :attr:`fields` property or by iterating
over the form object directly. Additionally, individual fields can be obtained
using ``form[key]`` syntax where *key* is the field name.

.. code-block::

    >>> form = service.form
    >>> for field in form:
    ...     print("%s: %s" % (field.name, field.type))
    input-file: FieldType.FILE
    num-steps: FieldType.INTEGER
    variation: FieldType.DECIMAL
    verbose: FieldType.BOOLEAN
    >>> form['num-steps']
    IntegerField(name='num-steps', label='Number of simulation steps',
                 description='', required=True, default=1000, min=0, max=10000)

In order to provide the input values for the form, you can set the value of
the field using item assignment ``form[key] = value`` syntax or using
:obj:`set(key, value)` method, where *key* is the field name and *value*
is the value to be set. This method replaces the old value with the new one.
The *value* can be either a type corresponding to
the field type or a collection of such values if multiple values are allowed.
In most cases the following types are expected for each field:

:IntegerField: :class:`int`
:DecimalField: :class:`float`
:TextField: :class:`str`
:BooleanField: :class:`bool`
:ChoiceField: :class:`str`
:FileField: :class:`str` (file uuid) or :class:`.File` or :class:`io.IOBase`

However, these values might differ depending on the service requirements
and custom server-side validation. For more information refer to the service
documentation on the particular server you want to access.

If the field accepts multiple values, you can either set it to the list of values using
the method above or you can use :obj:`Form.append(key, value)` to
append a single value or :obj:`Form.extend(key, iterable)` to append all values
from the *iterable* to the end of the values list. Keep in mind that
:meth:`.append` and :meth:`.extend` methods use the respective methods of the
underlying lists in the *values* dictionary. If the value was previously set to something
that doesn't implement :class:`MutableSequence` those methods will raise
:exc:`AttributeError`.

The inserted values can be removed using item deletion ``del form[key]``
or :obj:`delete(key)` method.
Additionally, using :obj:`clear()` will delete all values.

Internally, the values are stored in the :class:`.defaultdict`
having an empty list as a default factory.
That dictionary may be accessed and manipulated directly (it's not recommended though)
through the :attr:`values` attribute of the :class:`Form` object.

Once the form is populated, a new job request can be submitted to the server using
:meth:`~.Form.submit` method that returns job uuid or raises an exception if the submission
was not successful.
Additionally, you can supply one-off input values passing a mapping
as an argument or providing the values as keyword arguments. Those will
be added on top of the existing field values.

.. code-block:: python

    >>> form['input-file'] = open('/path/to/input.txt', 'rb')
    >>> form['num-steps'] = 100
    >>> form.extend('variation', [0.1, 0.2, 0.3])
    >>> job_id = form.submit(verbose=True)
    >>> job_id
    '1WsqR3H2RwOxTps1XI22xQ'


Retrieving job state and result
-------------------------------

Once the job is successfully submitted its state can be checked using
:meth:`.SlivkaClient.get_job_state` which takes job uuid returned by
:meth:`.Form.submit` and returns the :class:`.JobState`.

You can also fetch the list of results even if the job is still running
using :meth:`.SlivkaClient.get_job_results` and passing it job uuid.
Keep in mind that the results may be incomplete when the job is in
unfinished state.
The method returns the list of file handlers that can be used to inspect
files' metadata and stream their content.

Using File objects
------------------
Instead of working with files directly, Slivka assigns a uuid to each file and
uses it instead. This approach helps to avoid sending the same data
over the internet multiple times and allows using the output of one service
as an input to the other without the need to download and re-upload the file.

On the client side, files that are present on the server are
represented as :class:`File` instances. You obtain them when uploading
the file to the server or retrieving job results.
Those object are subclasses of string and are equal to file's uuid.
They also provide additional properties with file meta-data such as
:attr:`title`, :attr:`label`, :attr:`media_type` and
:attr:`url`.

The :class:`File` objects, however, does not store file content. If you
want to download the content either to the file, or to the memory you
can use :meth:`dump` method and pass it either path to the output file
or an open writable stream. It's highly recommended to use binary streams,
but in many cases text streams should work as well.

Example of uploading and downloading the file from the server:

.. code-block:: python

    >>> file = client.upload_file(open('/path/to/file.txt'))
    >>> file
    File(uploaded, [b2uEAxmrS6mZzLIqkkbfXQ])

    >>> # save to the file at the specified location
    >>> file.dump('/path/to/output.txt')

    >>> # open the file for writing and write to it
    >>> with open('/path/to/output_file.txt', 'wb') as fp:
    ...    file.dump(fp)

    >>> import io
    >>> # create in-memory buffer and write to it
    >>> stream = io.BytesIO()
    >>> file.dump(stream)
    >>> content = stream.getvalue()


If you want to use the same input file multiple times, it's a good idea
to upload it once and re-use the file handler to speed up the submission
process, save time and bandwidth. The submission form can accept
:class:`File` objects as well as open streams.


API Reference
=============

.. py:currentmodule:: slivka_client

.. py:class:: SlivkaClient(url)
              SlivkaClient(*, scheme, auth, host, port, path)

    .. autoattribute:: url
    .. autoattribute:: services
    .. automethod:: refresh_services
    .. automethod:: upload_file
    .. automethod:: get_file
    .. automethod:: get_job_state
    .. automethod:: get_job_results

.. autoclass:: Service()
    :members:
    :undoc-members:

.. autoclass:: Form()
    :members:
    :special-members: __iter__, __getitem__, __setitem__, __delitem__
    :undoc-members:

.. autoclass:: FieldType
    :members:
    :undoc-members:

.. autoclass:: JobState
    :members:
    :undoc-members:

.. autoclass:: File()
    :members:
    :undoc-members:

Form Fields
-----------
.. py:currentmodule:: slivka_client.form

.. autoclass:: _BaseField()
    :members:

.. autoclass:: UndefinedField()
    :members:

.. autoclass:: IntegerField()
    :members:

.. autoclass:: DecimalField()
    :members:

.. autoclass:: TextField()
    :members:

.. autoclass:: BooleanField()
    :members:

.. autoclass:: ChoiceField()
    :members:

.. autoclass:: FileField()
    :members:
