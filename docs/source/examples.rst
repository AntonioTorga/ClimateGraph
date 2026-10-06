Examples
========

One example per plot type. Each figure below was produced by running the control
file shown beneath it — nothing is hand-drawn or touched up afterwards.

The data is synthetic. It is shaped like winter air quality over the Santiago
basin (a two-peaked daily cycle, cleaner weekends, pollution pooling in the low
western side of the valley), but the numbers are invented. Real data would make
these prettier and no clearer.

Running them yourself
---------------------

The datasets are small and live in the repository, so the examples work straight
from a clone. From the repository root:

.. code-block:: console

   $ python docs/examples/make_data.py                     # only needed once
   $ ClimateGraph run docs/examples/configs/timeseries.yaml

Figures land in ``docs/examples/output/<plot name>/``. To rebuild every figure on
this page at once:

.. code-block:: console

   $ python docs/examples/generate_figures.py

Timeseries
----------

Two datasets over time, one line each. By default every dataset is reduced over
*its own* geometry, so this is the station-network mean against the whole-grid
mean — which is why the model sits consistently above the observations. The grid
covers the polluted western side of the basin where there are no stations.

.. image:: /_static/examples/timeseries.png
   :alt: Hourly PM2.5 for stations and model over ten days
   :width: 100%

.. literalinclude:: ../examples/configs/timeseries.yaml
   :language: yaml
   :caption: docs/examples/configs/timeseries.yaml

Time cycle
----------

The average day, built by grouping every timestamp into its hour bucket. The
first dataset listed is the reference and gets a standard-deviation band; the
rest are drawn as plain lines.

.. image:: /_static/examples/timecycle.png
   :alt: Mean diurnal cycle of PM2.5 with a standard deviation band
   :width: 100%

.. literalinclude:: ../examples/configs/timecycle.yaml
   :language: yaml
   :caption: docs/examples/configs/timecycle.yaml

Scatter
-------

Value against value for exactly two datasets, with the one-to-one line for
reference.

This is the same model and the same stations as the timeseries above, but here a
domain samples the model grid *at the station locations* first. Co-located, the
model reads slightly low — the opposite of what the uncolocated timeseries
suggests. Comparing a grid mean to a station mean compares two different things.

.. image:: /_static/examples/scatter.png
   :alt: Modelled against observed PM2.5 with a one-to-one line
   :width: 70%
   :align: center

.. literalinclude:: ../examples/configs/scatter.yaml
   :language: yaml
   :caption: docs/examples/configs/scatter.yaml

Spatial map
-----------

A single dataset on a map. A gridded dataset is drawn with filled contours; a
station dataset would be drawn as coloured points from the same configuration.

.. image:: /_static/examples/spatial-map.png
   :alt: Map of modelled PM2.5 across the domain
   :width: 75%
   :align: center

.. literalinclude:: ../examples/configs/spatial-map.yaml
   :language: yaml
   :caption: docs/examples/configs/spatial-map.yaml

Spatial overlay
---------------

A gridded field with station observations drawn on top, sharing one colour
scale, so model and measurement can be read against each other directly.
``drop_nans`` removes stations with no observation in the window, so empty sites
neither draw nor stretch the extent.

.. image:: /_static/examples/spatial-overlay.png
   :alt: Station observations drawn over the modelled PM2.5 field
   :width: 75%
   :align: center

.. literalinclude:: ../examples/configs/spatial-overlay.yaml
   :language: yaml
   :caption: docs/examples/configs/spatial-overlay.yaml

Custom composition
------------------

Instead of picking a plot type, describe the figure. Each entry under
``subplots`` is a primitive drawn onto shared axes, and ``x`` names the
coordinate that goes on the horizontal axis. Everything not bound to an axis is
reduced away.

This example composes two line series, but the same mechanism overlays filled
contours and scattered points, and the axes can be any coordinate rather than
always time.

.. image:: /_static/examples/custom.png
   :alt: Two line series composed onto shared axes
   :width: 100%

.. literalinclude:: ../examples/configs/custom.yaml
   :language: yaml
   :caption: docs/examples/configs/custom.yaml
