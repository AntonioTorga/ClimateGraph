Utilities
=========

:mod:`ClimateGraph.utils`

Purpose
-------

The necessary tools shared by more than one main module. 
Everything here is used by more than one part of the
framework, and nothing here knows about the framework's own objects — these
operate on xarray, pandas and paths.

Keeping them separate is what lets the readers, the domains and the plots apply
the same transform and get the same result.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Module
     - Holds
   * - :mod:`~ClimateGraph.utils.general_utils`
     - Enums, path expansion and time parsing
   * - :mod:`~ClimateGraph.utils.dataset_utils`
     - Transforms on xarray objects
   * - :mod:`~ClimateGraph.utils.resample_engine`
     - Pluggable spatial resampling backends
   * - :mod:`~ClimateGraph.utils.registry`
     - The registry mixin — see :doc:`registry`
   * - :mod:`~ClimateGraph.utils.parser` / :mod:`~ClimateGraph.utils.control_model`
     - Configuration — see :doc:`parser`

General utilities
-----------------

The enums — ``TimestepEnum``, ``TimeBucketEnum``, ``ReductionMethodEnum`` and
``CRSEnum`` — are how the config's string values become real objects.
``ReductionMethodEnum`` carries the function alongside the name, so a config
saying ``mean`` yields something callable rather than a string to switch on.

:func:`~ClimateGraph.utils.general_utils.manage_path` expands a path, a glob or
a list of either into a concrete list of existing files, which is why ``path:``
accepts all three forms.

The time handling is the subtle part.
:func:`~ClimateGraph.utils.general_utils.manage_time_interval` turns a string
into a start and end pair, and treats a coarse date as *the interval covering its
own resolution* — so ``"6/2021"`` means all of June rather than an instant.
:func:`~ClimateGraph.utils.general_utils.normalize_time` turns a single entry or
a list into the list form the plots iterate over, which is what makes time
fan-out work.

Dataset transforms
------------------

These are the steps a dataset passes through between being read and being drawn:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Function
     - Does
   * - ``dim_reduction``
     - Per-dimension selection or reduction, before any blanket reduce
   * - ``time_resampling``
     - Resample onto a timestep and clip to a time interval
   * - ``change_unit``
     - Convert between pint units
   * - ``apply_operation``
     - Arithmetic declared in the config, applied at read time
   * - ``variable_aggregation``
     - Combine variables according to an aggregation mapping
   * - ``normalize_vars``
     - Bring the three accepted ``vars`` forms to one internal shape

``apply_operation`` parses the expression through Python's AST and evaluates only
the node types it allows, so a config string cannot execute arbitrary code.

``_record`` appends a timestamped line to the dataset's ``history`` attribute at
every mutating step. A dataset written out with ``save_to`` therefore carries a
trace of everything that was done to it.

Resample engines
----------------

:class:`~ClimateGraph.utils.resample_engine.ResampleEngine` is a protocol with
two methods, ``prepare`` and ``make_resampler``.
:class:`~ClimateGraph.utils.resample_engine.PyresampleEngine` is the only
implementation today, offering nearest-neighbour and gaussian resampling over a
KD-tree.

The indirection exists so another backend can be added without touching
:meth:`~ClimateGraph.data.Data.resample_vars`, which takes the engine by name.

Keep in mind
------------

Dates are day-first
   ``"6/1/2021"`` is the sixth of January, not the first of June.

A coarse date spans its bucket
   ``"2021"`` covers the whole year and ``"6/2021"`` the whole month. Endpoints
   of a range are each expanded on their own resolution, and a warning is logged
   when the two differ.

Unit conversion needs a declared unit
   A variable with no ``unit`` is passed through untouched; conversion is only
   possible when the source unit was declared.
