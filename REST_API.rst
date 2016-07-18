
========
REST API
========

``GET /services``
-----------------

**Description**

Gets the list of available services.

**Parameters**

None

**Responses**

200
::

  {
    "services": [string]
  }

============  ================================
``services``  List of available service names.
============  ================================

``GET /service/{service}/form``
-------------------------------

**Description**

Get service request form

**Parameters**

+-------------+--------+---------------+
| Name        | Value  | Description   |
+=============+========+===============+
| *Path parameters*                    |
+-------------+--------+---------------+
| ``service`` | string | Service name. |
+-------------+--------+---------------+

**Responses**

200
::

  {
    "form": string,
    "service": string,
    "fields" [
      {
        "name": string,
        "type": string,
        "required": boolean,
        "default": (string|int|boolean),
        "constraints": [
          constraintObject
        ]
      }
    ]
  }

========================  ============================
``form``                  Name of the form.
``service``               Name of the service.
``fields``                List of form fields.
``fields[].name``         Field name.
``fields[].type``         Field type.
``fields[].required``     If the field is required.
``fields[].default``      Default value.
``fields[].constraints``  List of `constraint objects`_
========================  ============================

.. _constraint objects:

**Constraint object** can be one of the following objects, depending on the
value type and constraint type ::

  {
    "name": ("max"|"min"|"maxLength"|"minLength"|"maxSize"),
    "value": int
  }

  {
    "name": ("minExclusive"|"maxExclusive"),
    "value": boolean
  }

  {
    "name": ("mimetype"|"extension"),
    "value": string
  }

  {
    "name": "choices",
    "value": [string]
  }


404 - Service ``{service}`` does not exist.::

  {
    "error": "not found"
  }

``POST /service/{service}/form``
--------------------------------

**Description**

Post new job request.

**Parameters**

+-------------+--------+------------------------------+
| Name        | Value  | Description                  |
+=============+========+==============================+
| *Path parameters*                                   |
+-------------+--------+------------------------------+
| ``service`` | string | Service name.                |
+-------------+--------+------------------------------+
| *Query parameters*                                  |
+-------------+--------+------------------------------+
| (field)     | string | Field name and value as they |
|             |        | were specified in the form   |
+-------------+--------+------------------------------+

**Responses**

202 - Form is valid, new task is added to the queue.::

  {
    "taskId": string
  }

==================  =====================================
``task_id``         Id of newly created task.
==================  =====================================

420 - Form is not valid, response contains errors list.::

  {
    "errors": [
      {
        "field": string,
        "value": (string|int|boolean),
        "errorCode": string,
        "message": string
      }
    ]
  }

=======================  ===============================
``errors``               List of form validation errors.
``errors[].field``       Name of the field.
``errors[].value``       Field value.
``errors[].error_code``  Error code.
``errors[].message``     Error description.
=======================  ===============================

404 - Service ``{service}`` does not exist.::

  {
    "error": "not found"
  }

``POST /file``
--------------

**Description**

Uploads a new file to the server. Client receives file id which should be
used to access or refer to the file.

**Parameters**

+-----------------+--------+---------------------------------------+
| Name            | Value  | Description                           |
+=================+========+=======================================+
| *Query parameters*                                               |
+-----------------+--------+---------------------------------------+
| ``mimetype``    | string | Mime type of the file.                |
+-----------------+--------+---------------------------------------+
| ``file``        | file   | File content                          |
+-----------------+--------+---------------------------------------+

**Responses**

203 - File was uploaded properly.::

  {
    "id": string,
    "signedId": string,
    "title": string,
    "description": string,
    "mimetype": string,
    "filename": string
  }

===============  ========================
``id``           Unique file identifier.
``signedId``     Signed file identifier.
``title``        Title of the new file.
``mimetype``     Mime type of the file.
===============  ========================

400 ::

  {
    "error": "no mimetype"
  }

400 ::

  {
    "error": "file is missing"
  }

415 ::

  {
    "error": "invalid mimetype"
  }


``GET /file/{file_id}``
-----------------------

**Description**

Get file metadata

**Parameters**

+-------------+--------+------------------------------------+
| Name        | Value  | Description                        |
+=============+========+====================================+
| *Path parameters*                                         |
+-------------+--------+------------------------------------+
| ``file_id`` | string | Unique file identification number. |
+-------------+--------+------------------------------------+

**Responses**

200
::

  {
    "id": string,
    "title": string,
    "mimetype": string
  }

===============  =================
``id``           File identifier.
``title``        File title.
``mimetype``     File mime-type.
===============  =================

404
::

  {
    "error": "not found"
  }


``GET /file/{file_id}/download``
--------------------------------

**Description**

Download the file

**Parameters**

+------------+--------+-----------------+
| Name       | Value  | Description     |
+============+========+=================+
| *Path parameters*                     |
+------------+--------+-----------------+
| ``fileId`` | string | File identifier |
+------------+--------+-----------------+

**Responses**

200 - Content of the file

404
::

  {
    "error": "not found"
  }


``PUT /file/{signed_file_id}``
------------------------------

**Description**

Updates file metadata. Can be used for annotating job results.

**Parameters**

+--------------------+--------+-------------------------------------------+
| Name               | Value  | Description                               |
+====================+========+===========================================+
| *Path parameters*                                                       |
+--------------------+--------+-------------------------------------------+
| ``signed_file_id`` | string | Signed file identification number.        |
+--------------------+--------+-------------------------------------------+
| *Query parameters*                                                      |
+--------------------+--------+-------------------------------------------+
| ``title``          | string | New title of the file. *(optional)*       |
+--------------------+--------+-------------------------------------------+

**Responses**

200
::

  {
    "id": string,
    "title": string,
    "mimetype": string
  }

===============  =================
``id``           File identifier.
``title``        File title.
``mimetype``     File mime type.
===============  =================

403 - Identifier signature is invalid.::

  {
    "error": "invalid signature"
  }

404 - File with id ``{signed_file_id}`` does not exist.::

  {
    "error": "not found"
  }


``DELETE /file/{signed_file_id}``
---------------------------------

**Description**

Permanently deletes the file from the server.
All tasks associated with this file will fail to execute.

**Parameters**

+--------------------+--------+------------------------------------+
| Name               | Value  | Description                        |
+====================+========+====================================+
| *Path parameters*                                                |
+--------------------+--------+------------------------------------+
| ``signed_file_id`` | string | Signed file identification number. |
+--------------------+--------+------------------------------------+

**Responses**

204 - File deleted successfully

403 - Identifier signature is invalid.::

  {
    "error": "invalid signature"
  }

404 - File with id ``{signed_file_id}`` does not exist.::

  {
    "error": "not found"
  }


``GET /task/{task_id}``
-----------------------

**Description**

Gets the status of the running task

**Parameters**

+-------------+--------+--------------------------------------+
| Name        | Value  | Description                          |
+=============+========+======================================+
| *Path parameters*                                           |
+-------------+--------+--------------------------------------+
| ``task_id`` | string | Task id received on form submission. |
+-------------+--------+--------------------------------------+

**Responses**

200
::

  {
    "status": ("pending"|"running"|"failed"|"completed"),
    "ready" boolean,
    "output": {
      "returnCode": int,
      "stdout": string,
      "stderr": string,
      "files": [string]
    }
  }

=====================  =======================================
``status``             Task execution status.
``ready``              Indicates whether the task is finished.
``output``             Task output.
``output.returnCode``  Return code
``output.stdout``      Standard output stream value.
``output.stderr``      Standard error stream value.
``files``              List of output file identifiers.
=====================  =======================================

404 - Task with id ``{task_id}`` does not exist.::

  {
    "error": "not found"
  }

