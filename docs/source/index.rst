ClimateGraph
============

**ClimateGraph** is a modular Python framework for **reading**, **transforming** and
**visualizing** **climate and environmental data** from multiple sources and multiple topologies.

A single control file (a mapping file, can be YAML or JSON) declares *what data to read*, *how to subset it in
space and time*, and *what to plot from it*. ClimateGraph resolves the rest: it loads each dataset
lazily through a topology-source-appropriate reader, resamples between grids and station
networks where a comparison requires it, and writes the figures out.

.. code-block:: yaml

   analysis:
     output_path: "./results/run1"

   data:
     STATIONS:
       path: "./data/sinca-network-2021.nc"
       topology: PointSurface
       reader: sinca
       vars: {PM25: {name: pm25, unit: "ug/m**3"}}

   plots:
     pm25_series:
       type: timeseries
       data: STATIONS
       time: "1/6/2021 - 30/6/2021"
       vars: {PM25: "ug/m**3"}

.. code-block:: console

   $ ClimateGraph run config.yaml

.. image:: /_static/examples/timeseries.png
   :alt: Hourly PM2.5 from a station network and a model, over ten days
   :width: 100%

A control file like the one above is all it takes to get there. See
:doc:`examples` for one of each plot type, each with the configuration that
produced it.

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   getting-started/installation
   getting-started/quickstart

.. toctree::
   :maxdepth: 2
   :caption: About ClimateGraph

   reference/control-file
   about/overview 
   about/credits

.. toctree::
   :maxdepth: 2
   :caption: API

   api/index

.. toctree::
   :maxdepth: 2
   :caption: Examples

   examples