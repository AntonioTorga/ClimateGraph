Primitives
==========

:mod:`ClimateGraph.plot.primitive` — :mod:`ClimateGraph.plot.primitives`

Purpose
-------

A primitive is one drawable layer. Where a named plot type decides both what to
compute and how it looks, a ``type: custom`` plot lets several primitives be
composed onto shared axes, so a figure can be described rather than chosen from
a list. Provides more flexibility for the user. The idea would be that Plots also
use primitives underneath in the future.

The division of labour
----------------------

A primitive does **no data processing**. The plot resolves the dataset and
variable, applies the domain, filters time, reduces dimensions and converts
units, then hands the prepared :class:`xarray.DataArray` to ``render`` along with
the coordinate names bound to each axis.

``render`` draws and returns the matplotlib artist. Nothing else.

That keeps anything figure-level (legends, colorbars, axis decoration) as an
orchestrator's concern, which is what allows several primitives to share one set
of axes without fighting over them.

.. code-block:: text

   Custom plot                          Primitive
   ───────────                          ─────────
   resolve dataset + var
   apply domain
   filter time
   reduce dims
   convert unit
        │
        └── prepared DataArray ───────▶ render(ax, data, x=, y=, label=)
                                             └── returns the artist

The primitives
--------------

.. list-table::
   :header-rows: 1
   :widths: 20 25 55

   * - Type
     - Needs
     - Draws
   * - ``series``
     - ``x``
     - A line along one dimension
   * - ``contourf``
     - ``x`` and ``y``
     - Filled contours over two coordinates
   * - ``points``
     - ``x`` and ``y``
     - Coloured points at two coordinates

Each declares ``required_coords``, which the plot checks before preparing
anything, and whether it wants a legend or a colorbar so the orchestrator can
add one.

Axis freedom
------------

The reason primitives exist is that ``x`` and ``y`` name **coordinates**, not
fixed roles. A coordinate may be two-dimensional — longitude over ``(y, x)``, for
instance — and everything not bound to an axis is reduced away.

So the same data can be drawn against time, against height, or against another
coordinate entirely, without a new plot type for each combination.

Adding a primitive
------------------

.. code-block:: python

   class MyPrimitiveConfig(SubplotConfig):
       type: Literal["myprimitive"]

   class MyPrimitive(Primitive):
       config = MyPrimitiveConfig
       aliases = ["myprim"]
       required_coords = frozenset({"x"})
       wants_legend = True

       def render(self, ax, data, *, x, y, label):
           ...

The same registry machinery as the other families applies — see
:doc:`registry`. The subplot config models are gathered into a discriminated
union, so the new type becomes valid in a ``subplots:`` list immediately.

Keep in mind
------------

Variable scope is mutually exclusive
   Either the plot sets ``vars`` and re-renders the whole composition once per
   variable, or each subplot sets its own ``var`` for a fixed composition. Never
   both.

Styling passes through
   Unrecognised subplot keys are collected and forwarded to matplotlib, so
   ``color``, ``linewidth`` and friends work without being declared.
