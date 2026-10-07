Credits
=======
ClimateGraph was conceived under the umbrella of Fondecyt Project 1231717,
directed by Nicolas Huneeus.

Funding
-------

This project is funded by ANID (Agencia Nacional de Investigación y Desarrollo)
Chile, through the FONDECYT Regular project N° 1231717.


Author
------

Antonio Andrés Torga Mellado
(`antonio.torga@ug.uchile.cl <mailto:antonio.torga@ug.uchile.cl>`_)
Nicolas Huneeus

Data sources
------------

ClimateGraph reads data from the following models and monitoring networks. The
data itself is not distributed with the software, and remains the property of the
organizations that produce it.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Source
     - Description
   * - WRF
     - Weather Research and Forecasting model output
   * - CHIMERE
     - CHIMERE chemistry-transport model output

Built with
----------

ClimateGraph is built on the scientific Python stack, and would not be practical
without it:

`xarray <https://xarray.dev>`_ for labelled N-dimensional data ·
`pandas <https://pandas.pydata.org>`_ ·
`NumPy <https://numpy.org>`_ ·
`dask <https://www.dask.org>`_ for parallel and out-of-core computation ·
`matplotlib <https://matplotlib.org>`_ for rendering ·
`cartopy <https://scitools.org.uk/cartopy/>`_ for map projections ·
`pyresample <https://pyresample.readthedocs.io>`_ for spatial resampling ·
`regionmask <https://regionmask.readthedocs.io>`_ and
`geopandas <https://geopandas.org>`_ for region masking ·
`pint <https://pint.readthedocs.io>`_ for units ·
`Pydantic <https://docs.pydantic.dev>`_ for configuration validation ·
`Typer <https://typer.tiangolo.com>`_ for the command line interface.

License
-------

ClimateGraph is released under the MIT License. See the ``LICENSE`` file in the
repository.
