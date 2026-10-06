AppKernel
=========

:mod:`ClimateGraph.appkernel`

Purpose
-------

:class:`~ClimateGraph.appkernel.AppKernel` handles the main routine loop connecting the modules of the
application to each other. It holds the registries of every instance the parser
built — the datasets, the domains and the plots — and it sets up the
run-scoped settings those instances depend on: where output goes, whether debug logging is on, amount of dask threads to use if wanted.

Nothing here knows how to read a file or draw a figure. The kernel's job is to
orchestrate the ones who do know.

The run loop
------------

:meth:`~ClimateGraph.appkernel.AppKernel.run` is the main loop of the
application:

.. code-block:: text

   read_control(path)        parse and validate the config, build the registries
        ↓
   set_analysis_data()       promote the analysis block to kernel settings
        ↓
   debug_override or debug   resolve the effective debug level
        ↓
   _configure_logging()      scope DEBUG to ClimateGraph's own logger
        ↓
   with _dask_client():      start a cluster only if workers was requested
        plot()               dispatch one job per plot
        ↓
   clear registries          drop the datasets, domains and plots

Plotting is the only kind of job dispatched today. Analysis jobs are the
intended next one.

Global settings
---------------

:meth:`~ClimateGraph.appkernel.AppKernel.set_analysis_data` copies the control
file's ``analysis`` block onto the kernel, where the rest of the run reads it:

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Setting
     - Default
     - Meaning
   * - ``output_path``
     - required
     - Root directory for figures; each plot writes to a subdirectory named after it.
   * - ``debug``
     - ``False``
     - Raise ClimateGraph's own logger to DEBUG.
   * - ``workers``
     - ``None``
     - Number of dask threads. ``None`` means no cluster at all.

The ``analysis`` block is validated by
:class:`~ClimateGraph.utils.control_model.AnalysisModel`. No extra vars or mispelled vars
are accepted here.

Registries
----------

After parsing, the kernel holds three dictionaries keyed by the names chosen in
the control file:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute
     - Contents
   * - ``data``
     - ``{name: Data}`` — one per ``data`` block. Lazy; nothing is read yet.
   * - ``domains``
     - ``{name: Domain}`` — one per ``domains`` block, after fan-out expansion.
   * - ``plots``
     - ``{name: Plot}`` — one per ``plots`` block, each already holding references to the data and domain registries it needs.

Plots reach their datasets and domains through these registries, which is what
lets the control file refer to everything by name.
