Data
====

:mod:`ClimateGraph.data`

Purpose
-------

:class:`~ClimateGraph.data.Data` abstracts the idea of a dataset, independent of
the format it arrived in, the file layout it was stored in, and the shape of the
thing it describes. It brings everything into a common set of dimensions, and it
is the interface the rest of the framework talks to.

The goal is that a plot can say *draw a line/map/etc over this domain comparing X and Y*
without knowing anything about how X and Y are structured, or that they are
structured differently from each other.

Topology
--------

The organising abstraction is **topology** — the shape of the thing the data
describes. A set of stations, a regular grid and a satellite swath behave
differently enough that they belong in different topology types, and the interactions
*between* those buckets have to be standardized. Inside a bucket, though, there
is room to make everything uniform: all regular grids can be addressed by ``x``,
``y``, ``z`` and ``time``.

Each topology is a subclass declaring which of its dimensions are *geometry*:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Topology
     - ``geom_dims``
     - Geometry
   * - :class:`~ClimateGraph.data.RegularGrid`
     - ``("x", "y")``
     - Structured latitude/longitude grid
   * - :class:`~ClimateGraph.data.PointSurface`
     - ``("site",)``
     - Stations, as one-dimensional site coordinates
   * - :class:`~ClimateGraph.data.SatelliteSwath`
     - none
     - Not currently usable; see below

``geom_dims`` is what makes the rest general. Only those dimensions are treated
as spatial, so anything else a dataset happens to carry — vertical levels, time,
ensemble members — passes through operations untouched instead of needing special
handling.


Getting values out
------------------

:meth:`~ClimateGraph.data.Data.get_var` is the accessor the plots use. It takes a
variable by the name the control file gave it and applies, in order, the
per-dimension reductions, the blanket reduction over whatever dimensions are left,
and the unit conversion. What comes back is ready to draw.

This is where the abstraction pays off: the caller asks for a variable reduced to
the dimensions it wants, and does not care whether the spatial dimensions it
reduced away were ``x``/``y`` or ``site``.

A ``Data`` object is constructed from the control file but reads nothing. The
``obj`` property loads on first access, through the reader the dataset declared. So this is
the most probable first access to data and so the first get_var would trigger the read and take a little longer.

Resampling between datasets
---------------------------

:meth:`~ClimateGraph.data.Data.resample_vars` projects another dataset's variables
onto this one's geometry. It is purely spatial — the source keeps its own time
axis and inherits the target's spatial coordinates — and it is what allows a model
grid and a station network to be compared at all.

Because only ``geom_dims`` are treated as core dimensions, extra dimensions
broadcast through automatically rather than breaking the projection.

Results are memoized on the source, keyed by target, so several domains
reprojecting onto the same target pay for the projection once.
The resample cache lives on the *source* ``other._resample_cache``, not on the target.

Known limitation
----------------

The abstraction cannot cover satellite swath's yet. Committing to ``x``,
``y``, ``z`` and time makes a satellite swath very hard to represent, because a
swath's spatial coordinates *also* vary with time — the geometry moves. The
current model assumes geometry is fixed and time is just another dimension
alongside it.
