Class registries
================

:mod:`ClimateGraph.utils.registry`

Purpose
-------

:class:`~ClimateGraph.utils.registry.RegistryMixin` makes an abstract base class
keep a registry of the subclasses that inherit from it. Subclassing is enough to
be registered, and — for the families that declare config models — enough to
appear in the control file schema.

The point is that adding a capability touches one file. A developer writes the
subclass and nothing outside it has to change. Modularity wins

Building the schema
-------------------

:meth:`~ClimateGraph.utils.registry.RegistryMixin.build_config_union` collects the
``config`` model declared by every registered subclass and returns a Pydantic
discriminated union keyed on ``type``.

This is the mechanism behind the schema being distributed across the codebase.
:mod:`ClimateGraph.utils.control_model` does not enumerate the plot types; it
calls:

.. code-block:: python

   PlotModel = Plot.build_config_union()
   DomainModel = Domain.build_config_union()

so a new plot type's config model joins the control file schema as soon as its
class exists. ``Data`` has no per-subclass config and never calls this.

Adding a type
-------------

For a plot, domain or primitive, the whole contract is:

.. code-block:: python

   class MyPlotConfig(BasePlotConfig):
       type: Literal["myplot"]

   class MyPlot(Plot):
       config = MyPlotConfig
       aliases = ["mp"]

       def plot(self):
           ...

The class is registered under ``myplot`` and ``mp``, its config is part of the
validated schema, and ``type: myplot`` becomes usable in a control file.

Why Reader is different
-----------------------

:class:`~ClimateGraph.reader.Reader` keeps its own registration rather than using
this mixin, because its registry is two levels deep —
``{topology: {reader: class}}``. A reader name is only meaningful inside a
topology: ``default`` means something different for a regular grid than for a
point surface. The flat, single-namespace registry here cannot express that, so
``Reader`` implements the same idea with its own ``__init_subclass__``, which also
enforces that every reader declares the topology it belongs to.

