Plot
====

:mod:`ClimateGraph.plot`

Purpose
-------

A plot is the product of a run. It takes the datasets and domains the parser
built, reduces each dataset down to what the figure needs, draws it, decorates
the axes and writes the file.

The split mirrors the other families: :class:`~ClimateGraph.plot.Plot` is the
abstract base holding everything common to all figures, and each concrete plot
type lives beside its config model in ``plots.py``.


What the base provides
----------------------

A concrete plot implements ``plot()`` and inherits the rest:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Method
     - Provides
   * - :meth:`~ClimateGraph.plot.Plot.resolve_domains`
     - The domains this figure runs under, or a single ``None`` when it has none
   * - :meth:`~ClimateGraph.plot.Plot.iterate_contexts`
     - The product of times, domains and variables — one figure per combination
   * - :meth:`~ClimateGraph.plot.Plot.figure_kwargs` / :meth:`~ClimateGraph.plot.Plot.savefig_kwargs`
     - Matplotlib arguments, with the plot's own defaults overridden by the config
   * - ``_decorate_axes`` / ``_apply_grid``
     - Titles, labels, named ticks and grid lines
   * - ``_finalize`` / :meth:`~ClimateGraph.plot.Plot.savefig`
     - Decoration then writing, in one place

Fan-out
-------

A plot block does not necessarily produce one figure. Times, domains and
variables each multiply:

.. code-block:: text

   for time in times:
       for domain in domains:
           for var in vars:
               one figure

``iterate_contexts`` centralises that product so every plot type fans out
identically. Each concrete ``plot()`` is a thin loop over contexts, delegating
one figure to a ``_plot_one``.

The plot types
--------------

Every figure below is a real output. :doc:`../examples` shows the control file
that produced each one.

.. list-table::
   :header-rows: 1
   :widths: 20 38 42

   * - Type
     - Draws
     -
   * - ``timeseries``
     - One line per dataset over time, space reduced away
     - .. image:: /_static/examples/timeseries.png
          :alt: Two lines over time
   * - ``timecycle``
     - An average cycle over a time bucket; the first dataset gets a standard-deviation band
     - .. image:: /_static/examples/timecycle.png
          :alt: Mean diurnal cycle with a spread band
   * - ``scatter``
     - Value against value for exactly two datasets
     - .. image:: /_static/examples/scatter.png
          :alt: Modelled against observed values
   * - ``spatial-map``
     - One dataset on a map — filled contours for a grid, coloured points for stations
     - .. image:: /_static/examples/spatial-map.png
          :alt: Filled contour map of a modelled field
   * - ``spatial-overlay``
     - A gridded field with station points drawn over it
     - .. image:: /_static/examples/spatial-overlay.png
          :alt: Station points over a gridded field
   * - ``custom``
     - A composition of primitives on shared axes — see :doc:`primitives`
     - .. image:: /_static/examples/custom.png
          :alt: Two series composed on shared axes

The pipeline per figure
-----------------------

Within one context, each dataset goes through the same sequence before it is
drawn: the domain is applied, time is resampled, per-dimension reductions run,
whatever dimensions remain are reduced away, and the result is converted to the
requested unit.

The reduction step is where the topology abstraction pays off — a plot asks for a
variable reduced to the dimensions it wants without caring whether the spatial
dimensions it removed were ``x``/``y`` or ``site``.

Adding a plot type
------------------

.. code-block:: python

   class MyPlotConfig(BasePlotConfig):
       type: Literal["myplot"]

   class MyPlot(Plot):
       config = MyPlotConfig
       aliases = ["mp"]

       def plot(self):
           for ctx in self.iterate_contexts(...):
               self._plot_one(ctx)

Inheriting ``BasePlotConfig`` brings the shared fields — ``vars``, ``time``,
``domains``, ``dim_reduce``, the axis decoration and the matplotlib
passthroughs — so a new type declares only what is specific to it.

Keep in mind
------------

Co-location is not automatic
   A multi-dataset plot reduces each dataset over *its own* geometry by default,
   so a station-network mean is compared against a whole-grid mean. Sampling a
   model at the stations requires attaching a resampling domain — see
   :doc:`domain`.

Unknown fields are accepted silently
   Plot configs allow extra keys so they can be forwarded to matplotlib, which
   means a misspelled field name produces no error and no effect.
