Domain
======

:mod:`ClimateGraph.domain`

Purpose
-------

A domain defines a spatial subset of a dataset. It is applied per
plot, takes a :class:`~ClimateGraph.data.Data` and returns a new ``Data`` object, so a plot
can treat the result exactly like the dataset it started from (allows future composition of domains as well)

Two steps
---------

:meth:`~ClimateGraph.domain.Domain.apply` is a template with two steps:

.. code-block:: text

   if resample_to is set:
       data = _resample(data)      reproject onto another dataset's geometry
   return _filter(data)            subclass hook: narrow the data

``type`` in the config chooses the **filter**. Resampling is not a type: the
``resample_to`` field lives on the shared base config, so *every* domain type can
carry it.

That is why a pure reprojection is spelled ``type: all`` with a ``resample_to``
— ``All`` is the filter that keeps everything, so what remains is just the
reprojection.

The two steps compose, and the ordering is what makes the combination useful: a
filter can key on attributes that only exist *after* reprojection. Filtering a
model grid by a station attribute is impossible until the grid has been sampled
at the stations, and one domain expresses both.

``_resample`` caches results on the source, so several domains reprojecting onto the
same target pay for the projection once.

Keep in mind that resampling is a purely spatial operation, where the spatial dims are
defined by topology, and this op broadcasts through other dims. And that resampling from ``X`` to ``X`` is a no op,
and returns the original ``X`` as is.

The filters
-----------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Type
     - Filter
   * - ``attribute`` / ``attr``
     - Keep where a field matches a value
   * - ``polygon`` / ``poly``
     - Mask by polygons built from vertices
   * - ``shapefile`` / ``shp``
     - Mask from a field value in a shapefile
   * - ``points`` / ``pts``
     - Resample onto named points given inline or from a file
   * - ``all``
     - Keep everything

Each is a subclass pairing a config model with a ``_filter`` implementation, and
registers itself — see :doc:`registry`. ``All._filter`` is literally
``return data``.

Fan-out
-------

One domain block can expand into several domain objects, and a plot referencing
the original name then produces one output per expansion. The expansion happens
in the parser, before any domain object exists, so nothing here needs to know
about it — see :doc:`parser`.

Adding a domain
---------------

.. code-block:: python

   class MyDomainConfig(BaseDomainConfig):
       type: Literal["mydomain"]
       threshold: float

   class MyDomain(Domain):
       config = MyDomainConfig
       aliases = ["mydomain"]

       def _filter(self, data):
           ...

Inheriting ``BaseDomainConfig`` means the new type supports ``resample_to``
without doing anything, because the resample step belongs to ``apply`` rather
than to any filter.

Keep in mind
------------

``apply`` returns a new object
   Filtering produces a copy rather than mutating the dataset, so the same
   ``Data`` can be used by several plots under different domains.
