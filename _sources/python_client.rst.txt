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

Once the library is installed, you can import :class:`.SlivkaClient` from :mod:`slivka_client`
module and create its instance using a single *url* argument or provide
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


:class:`slivka_client.SlivkaClient` object is used for services discovery,
file uploading and retrieval and job monitoring.

Services listing and job submission
-----------------------------------

The list of available services can be accessed through the
:attr:`~.SlivkaClient.services` property of the :obj:`client` object.
The server will be contacted to provide the list of services on the first property access.
Subsequent attempts will return the cached list immediately.
Use :meth:`~.SlivkaClient.refresh_services` method whenever you want to reload
the list of services from the server.
If you need to fetch one service by its name you can use item access syntax
``client[key]`` where *key* is the service name.

.. code-block:: python

    >>> client.services
    [SlivkaService(clustalo), SlivkaService(mafft)]
    >>> service = client['clustalo']
    >>> service.name
    'clustalo'

Each :class:`.Service` object represents a single service on the server side.
They provide access to service information as well as the submission forms
needed to send new job requests to the server.

A :class:`.Form` stores the collection of parameters needed to run a job.
A new empty form is created every time :attr:`.Service.form` attribute is
accessed or :meth:`.Service.new_form` method is called.
Forms are dictionary-like objects providing a view of the service input parameters,
storing input values and mediating job submission to the server.
Iterating over the form directly or accessing :attr:`fields` gives
an iterable of fields each of them storing the information
about its corresponding input parameter and its constraints.
Individual field information may be retrieved using item access syntax
``form[key]`` where *key* is the field name.

Suppose that the ClustalO service takes the following parameters: *input-file*,
*dealign* and *iterations*.
Then, iterating over the form would produce the following output

.. code-block:: python

    >>> for field in form:
    ...     print(field)
    FileField(name='input-file', label='Input file', description'...',
              required=True, default=None, multiple=False,
              media_type='application/fasta', media_type_parameters={})
    BooleanField(name='dealign', label='Dealign input sequences',
                 description='...', required=False, default=False,
                 multiple=False)
    IntegerField(name='iterations', label='Number of iterations (combined)',
                 description='...', required=False, default=1, multiple=False,
                 min=1, max=100)

The properties common for all field objects are:

:type: type of the field (see :class:`~slivka_client.FieldType`)
:name: field name/identifier
:label: short human-readable label
:description: longer, more detailed description
:required: whether the field is required or not
:default: default value or ``None`` if not provided
:multiple: whether multiple values are accepted

Additionally, each field may have extra constrains according to its type.
All form fields and their respective properties are listed in the API Reference
section `Form Fields`_.

In order to provide the input values for the form, you can set the value of
the field using item assignment ``form[key] = value`` or calling form's
:obj:`set(key, value)` method, where *key* is the field name and *value*
is the value to be set. This method replaces the old value with the new one.
The *value* should be of the type matching the field type or a list of
such values whenever multiple values are allowed.
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
the method above or you can use :obj:`Form.append(key, value)` method to
append a single value or :obj:`Form.extend(key, iterable)` to append all values
from the *iterable* to the end of the values list.
Files can be provided using special :class:`File` objects described below
as well as passing open streams.

.. note::
    The client application will NOT attempt to seek to the beginning of the
    stream. It's up to the user to prepare the stream in the proper state
    before submitting the job.

Internally, the values are stored in the :class:`.defaultdict`
having an empty list as a default factory. That dictionary may be accessed
and manipulated directly (it's not recommended though)
through the :attr:`values` attribute of the :class:`.Form` object.
Keep in mind that methods :meth:`.Form.append` and :meth:`.Form.extend`
use the respective methods of the underlying lists in the *values* dictionary.
If the value was previously set to something not implementing
:class:`MutableSequence` those calls will raise :exc:`AttributeError`.

The inserted values can be removed using item deletion ``del form[key]``
or :obj:`delete(key)` method.
Additionally, :meth:`clear` deletes all the values from the form
and returns it to its initial state.

Once the form is populated, a new job request can be submitted to the server using
:meth:`.Form.submit` method that returns job uuid or raises an exception
if the submission was not successful.
Additionally, you can supply one-off input values passing a mapping
as an argument or providing the values as keyword arguments to
:meth:`~.Form.submit`. Those will be added on top of the existing field values
and will not persist in the form during consecutive submits.

Example of submitting the job to ClustalO service.
Two parameters *input-file* and *iterations* are stored in the form
while *dealign* is set for this single submission only.

.. code-block:: python

    >>> form['input-file'] = open('/path/to/input.txt', 'rb')
    >>> form['iterations'] = 100
    >>> job_id = form.submit(dealign=True)
    >>> job_id
    '1WsqR3H2RwOxTps1XI22xQ'


Retrieving job state and result
-------------------------------

Once the job is successfully submitted its state can be checked using
:meth:`.SlivkaClient.get_job_state` which takes job uuid returned by
:meth:`.Form.submit` and returns the :class:`.JobState`.

You can fetch the list of results even if the job is still running
using :meth:`.SlivkaClient.get_job_results` providing job uuid as an argument.
Keep in mind that the results may be incomplete when the job is in
unfinished state.
The method returns the list of file handlers (more information in the next
section) that can be used to inspect files' metadata and stream their content.

Working with File objects
-------------------------
Instead of working with files directly, Slivka assigns a uuid to each file and
uses it instead. This approach helps to avoid sending the same data
over the internet multiple times and allows using the output of one service
as an input to the other without the need to download and re-upload the file.

On the client side, files present on the server are
represented as :class:`File` instances. You obtain them when uploading
the file to the server or retrieving job results.
Those object are subclasses of string and are equal to file's uuid.
They also provide additional meta-data it their properties such as
:attr:`title`, :attr:`label`, :attr:`media_type` and
:attr:`url`.

The :class:`File` objects, however, does not store file content. If you
want to download the content either to the file, or to the memory you
can use :meth:`dump` method and pass it either the path to the output file
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
process, save time and bandwidth.


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

    .. py:method:: name() -> str
        :property:

        Name (identifier) of the service.

    .. py:method:: label() -> str
        :property:

        Human-friendly label.

    .. py:method:: url() -> str
        :property:

        Url where the service is available at.

    .. py:method:: classifiers() -> List[str]
        :property:

        List of tags or classifiers that the service has.
        They can be set arbitrarily by the server administrator
        to help identifying the service types.

    .. py:method:: new_form() -> Form
    .. py:method:: form() -> Form
        :property:

        Creates and returns new submission form. A new empty
        form is created every time the the property is accessed
        or the method is called.

    .. py:method:: refresh_form()

        Forces the form data to be reloaded from the server.


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
