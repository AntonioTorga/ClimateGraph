Quickstart
==========

Everything ClimateGraph does is driven by one control file. This page walks the
smallest useful one, then extends it to give a brief look into the versatility of ClimateGraph

A minimal control file
----------------------

Three blocks: where output goes, what data to read, what to draw.

.. code-block:: yaml

   analysis:
     output_path: "./results/quickstart/"

   data:
     CHIM:
       path: "./data/chim-20*.nc"
       topology: RegularGrid
       reader: chimere

   plots:
     map:
       type: spatial-map
       data: CHIM
       vars: PM25

- ``analysis.output_path`` is the only required setting in its block.
- ``data`` maps a **name you choose** (``CHIM``) to a dataset. ``topology`` says
  what shape the data has, ``reader`` says how to parse it, based on a set of supported data sources,
  and ``path`` accepts a single path, a glob, or a list.
- ``plots`` maps a **name you choose** (``map``) to a figure, referring to the
  dataset by the handle you gave it.

Omitting ``vars`` when defining a dataset (CHIM in this case) keeps every variable referable under its native name. 
Not easy to pull off when comparing one or more datasets (names must match natively)

Run it
------

.. code-block:: console

   $ ClimateGraph run config.yaml

Figures are written to ``output_path/<plot_name>/`` — here
``./results/quickstart/map/``. The filename encodes the variable and the
resolved time window unless you override it with ``filename``. Be careful with this because 
if a plot block produces more than one plot it can overwrite them (iterates through domains, vars, and time domains)

For verbose logging from ClimateGraph itself:

.. code-block:: console

   $ ClimateGraph run config.yaml --debug

Declaring variables and units
-----------------------------

Naming variables explicitly lets you rename them and attach units, which in turn
enables conversion at plot time:

.. code-block:: yaml

   data:
     SINCA:
       path: "./data/SINCA*.nc"
       topology: PointSurface
       reader: sinca
       vars:
         PM25:
           name: PM25_ug|m3
           unit: "ug/m**3"

``name`` is the variable as it appears in the file; ``PM25`` is what you call it
everywhere else in the config. ``unit`` is a `pint <https://pint.readthedocs.io>`_
unit string.

Comparing two datasets
----------------------

Add a second dataset and give the plot a list. A timeseries reduces each dataset
over space and draws one line per dataset:

.. code-block:: yaml

   plots:
     comparison:
       type: timeseries
       data: [SINCA, CHIM]
       time: "1/6/2021 - 30/6/2021"
       vars: {PM25: "ug/m**3"}

Dates are **day-first**. A bare coarse date spans its bucket, so ``"6/2021"``
means all of June 2021.

By default each dataset is reduced over *its own* geometry — a station-network
mean against a whole-grid mean. To sample the model *at the station locations*
instead, attach a resampling domain:

.. code-block:: yaml

   domains:
     at_stations:
       type: all
       resample_to: SINCA

   plots:
     comparison:
       type: timeseries
       data: [SINCA, CHIM]
       domains: [at_stations]
       time: "1/6/2021 - 30/6/2021"
       vars: {PM25: "ug/m**3"}

A domain does two things in order: an optional **reprojection**, requested with
``resample_to`` and available on every domain type, that reprojects from the spatial structure 
of one dataset to another, followed by a **filter**,
chosen with ``type``. ``all`` is the filter that keeps everything, so ``type:
all`` plus ``resample_to`` is a pure reprojection with no subsetting.

The two steps combine. Because ``region`` is an attribute of the *stations* and
does not exist on the model grid, filtering a model by it is only possible once
the grid has been sampled at the stations — one domain expresses both:

.. code-block:: yaml

   domains:
     region13_at_stations:
       type: attr
       resample_to: SINCA
       field_name: region
       field_value: 13

Where to go next
----------------

- :doc:`../reference/control-file` — every field of every block in the config file.
- :doc:`../about/overview` — how the pieces fit together internally.
