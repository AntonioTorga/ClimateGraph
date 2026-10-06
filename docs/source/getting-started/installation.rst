Installation
============

Requirements
------------

ClimateGraph has been tested with **Python 3.12 or newer** so that's what we recommend.

Clone the repository
--------------------

.. code-block:: console

   $ git clone https://github.com/AntonioTorga/ClimateGraph.git
   $ cd ClimateGraph

The committed ``.lfsconfig`` sets ``fetchexclude = *``, so the clone does **not**
download the Git LFS sample data (roughly 1.8 GB of NetCDF under
``test_data/data/``). You get a working checkout in seconds; see
:ref:`test-data` below if you want the samples.

To work on a branch:

.. code-block:: console

   $ git checkout -b my-feature

Install
-------

From the clone:

.. code-block:: console

   $ python -m venv venv
   $ source venv/bin/activate
   $ pip install -e .

Optional extras
---------------

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Extra
     - Contents
   * - ``dev``
     - ``ruff``, ``pre-commit`` — linting and the commit hooks
   * - ``test``
     - ``pytest``, ``pytest-cov``, ``pillow`` — the test suite
   * - ``docs``
     - ``sphinx``, ``furo``, ``sphinx-gallery``, ``pylint``, ``pydeps`` — this documentation

.. code-block:: console

   $ pip install -e ".[dev,test,docs]"

Verify installation
-------------------

.. code-block:: console

   $ ClimateGraph version
   ClimateGraph version 0.3.0

   $ ClimateGraph --help
   [all options available haha and descriptions]

.. _test-data:

Test data
---------

The NetCDF samples under ``test_data/data/`` are tracked with Git LFS and are
**excluded from clones by default** — ``.lfsconfig`` sets ``fetchexclude = *``.
The fast test suite and this documentation both run without them:

.. code-block:: console

   $ pytest -m "not slow"

To fetch them anyway:

.. code-block:: console

   $ git lfs pull --exclude=
