Reader
======

:mod:`ClimateGraph.reader`

Purpose
-------

A reader turns files on disk into an :class:`xarray.Dataset`. It is the other
half of :doc:`data` — where ``Data`` abstracts *what a dataset is*, a reader
handles *how this particular format and file layout is read*.

Readers are registered per topology, because a reader name is only meaningful
inside one.

The lifecycle
-------------

:meth:`~ClimateGraph.reader.Reader.read` is a template method. It walks a fixed
sequence of hooks and subclasses plug into the individual steps; no subclass
overrides ``read`` itself.

.. code-block:: text

   _resolve_paths      expand globs, download and cache remote paths
        ↓
   safe:   _open_many(paths)        xarray drives the per-file loop
   unsafe: per path:                the reader drives it
             _open_one
             _to_xarray
             _preprocess
           _join(pieces)
        ↓
   _postprocess        whole-dataset adjustments
        ↓
   _finalize           spec-driven transforms, runs for every reader

The two load modes differ only in **who drives the per-file loop**. In safe mode
xarray's ``open_mfdataset`` does it and calls the per-file hooks through its
``preprocess`` argument; in unsafe mode the reader loops itself and joins the
pieces. The same per-file hooks run either way.
There is nothing really safe or unsafe in either way, this is going to be renamed eventually,
but it's just a way of providing two paths for file reading.

``_finalize`` centralizes final operations over the resulting xr.Dataset:
time offsets, arithmetic operations, dimension reduction and the optional save.
It runs for every reader regardless of which hooks a subclass overrode.

ReadSpec
--------

:class:`~ClimateGraph.reader.reader.reader.ReadSpec` is the bundle of everything
a read needs: the paths, the variable declarations, the load mode, the cache
directory, the engine and a free-form ``extras`` dict carrying reader-specific
options from the control file.

It is passed to every hook. That is what keeps the hook signatures stable. So a
subclass that needs some new piece of configuration reads it off the spec rather
than requiring a new parameter threaded through the lifecycle.

The reader families
-------------------

There usually is a default reader for any kind of topology, so other readers can skip implementing topology-wide logic

**Regular grid** — :class:`~ClimateGraph.reader.reader.regular_grid.default.DefaultRegularGridReader`
is the base; ``Wrf`` and ``Chimere`` specialise it for those model outputs.

**Point surface** — :class:`~ClimateGraph.reader.reader.point_surface.default.DefaultPointSurfaceReader`
is the base for NetCDF station data, with ``DMC`` and ``SINCA`` as the network-specific
readers. ``CSVPointSurfaceReader`` extends it for tabular data, and the three
layout readers extend *that*, each differing only in how the files are arranged:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Reader
     - File layout
   * - ``station-per-file``
     - One file per station
   * - ``single-file``
     - One file containing every station
   * - ``variable-per-file``
     - One file per variable

The CSV readers generally need a metadata file supplying station coordinates,
since a table of values alone carries no geometry.

Adding a reader
---------------

Subclass the default for the topology, declare ``topology`` and any
``type_aliases``, and override only the hooks that differ:

.. code-block:: python

   class MyReader(DefaultRegularGridReader):
       topology = "RegularGrid"
       type_aliases = ["my-reader"]

       def _preprocess(cls, ds, spec):
           ...

Registration happens on class definition, and ``__init_subclass__`` enforces that
every reader declares a topology. The name becomes usable as ``reader:`` in a
control file immediately.
