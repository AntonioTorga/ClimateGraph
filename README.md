# 🌍 ClimateGraph

[![CI](https://github.com/AntonioTorga/ClimateGraph/actions/workflows/ci.yml/badge.svg)](https://github.com/AntonioTorga/ClimateGraph/actions/workflows/ci.yml)

**ClimateGraph** is a modular Python framework for reading, transforming, and visualizing climate and environmental data from multiple sources.

It is designed to be:

-  **Extensible** — easily add new data readers and plot types
-  **Topology agnostic** - compare data between different topology types with ease
-  **Config-driven** — controlled via YAML or JSON configuration files
-  **Lazy & efficient** — data is only loaded and processed when needed

---

##  Features

### Data Readers

- **WRF (Weather Research and Forecasting)** model outputs (gridded data)
- **CHIMERE** model outputs (gridded data)
- **DMC** and **SINCA** networks (point surface observations, NetCDF)
- **CSV / Excel in-situ data**: SINCA (Chile), São Paulo and Quito readers

- Designed for future support:
  - Satellite swath data
  - Additional NetCDF-based datasets

---

### 📊 Plot Types

- **Spatial Overlay**

  - Overlay point data over spatially distributed data.
  - Uses contour maps + scatter overlays

- **Spatial Map**

  - Single-dataset map of one variable.
  - `contourf` for gridded data, scatter for point data (picked from topology).

- **Timeseries**

  - Compare temporal evolution across datasets
  - Supports spatial resampling and time resampling and alignment.

- **Time Cycle**

  - Average cycle over a time bucket (hour, day, season, ...).
  - Std-deviation band on the base dataset; other datasets drawn as lines.

- **Scatter**

  - Dataset-to-dataset comparison
  - Useful for validation and bias analysis

---

### Data Handling

- Lazy data loading
- Time resampling and alignment
- Spatial Resampling (Cartopy and Pyresample based)
- Automatic unit conversion

---

## Installation

```bash
git clone https://github.com/AntonioTorga/ClimateGraph.git
cd ClimateGraph
pip install .
```

In cloning the git-lfs managed data isn't pulled. But if you want to run the configuration files inside of test_data/configs please run the following command:

```bash
git lfs pull --include "*" --exclude ""
```

---

## Repository structure

```bash
ClimateGraph/
├── ClimateGraph
    │
    ├── data/               # Data representation (WRF, DMC, etc.)
    ├── plot/               # Plot classes and logic
    ├── reader/             # Specific readers
    ├── utils/              # Pydantic models for YAML validation, parser, etc.
    ├── examples/           # Example YAML configs
    ├── appkernel.py        # The app core, orchestrating the communication between modules.
    └── cli.py              # Command line interface. Invoked by running (ClimateGraph run ...)
├── test_data               # Available YAML config file with corresponding test data and results.
├── tests                   # Pytest unit testing
... # other less important stuff

```

---

##  Usage

ClimateGraph is driven by a YAML or JSON configuration file that specifies the execution parameters. This control file has four key information blocks (soon to be four with domain definitions):

### - analysis
Configuration for overall execution.

 Managed parameters are as following:
   - output_path: Relative or absolute path to directory in which to leave the results.
   - debug: Boolean flag, turns on debug mode. Defaults to False (doesn't do much yet)

### - data
Every sub-block defines a new data item, which is composed by the following parameters:
  - topology: PointSurface, RegularGrid or SatelliteSwath (the latter is not yet supported)
  - reader: Specific reader for your data (WRF, Chimere, DMC, etc).
  - path: Relative or absolute path or list of paths. Accepts and expands hotkeys (*,?)
  - vars: Block of information about the vars about to plot. Every subblock defines a variable and includes **ONLY** the name of the variable in the files and the unit.
  - crs: Coordinate Reference System. Managed by Cartopy, currently only PlateCarree is available.
  - load_mode: `safe` (default) or `unsafe`. See the loading notes for the trade-offs.
  - time_offset (optional): hours to shift the `time` coordinate by, applied at read time. Meant for datasets stored in UTC that you want on a local schedule — e.g. `time_offset: -3` reads a UTC file as UTC-3 (Chile). Fractional hours are allowed (e.g. `5.5`); omit it or set `0` to leave time untouched.
  - Any other key in the data block (e.g. `engine`, `cache_dir`, `vertical_level`, `metadata`) is passed through to the reader as a reader kwarg.
### - domains
  - **type** Type of domain.
  And then every different type requires different extra arguments.
- Attribute Domain (referred as "attribute" or "attr"):
  - field_name: Attribute field name present in the obj.
  - field_value: Value of the attribute selected.
- Polygon Domain (referred as "polygon" or "poly") :
  - vertex: List of tuples of floating numbers. Each tuple defines a vertex in (lon, lat). Can also manage a List of List of Tuples, that defines a Multipolygon.
- Shapefile Domain (referred as "shapefile" or "shp"): (Not tested)
  - path: pathlib.Path to the shapefile.
  - field_value: field value to filter the data by.

### - plots
All plots require different arguments, but they all manage the following base parameters:
  #### Very important parameters
  - **type**: Type of plot. Every plot has a default name and some aliases (listed below for every plot type) that work as this argument. This parameter is not case sensitive.
  - **vars**: a single string, a list of strings or a dictionary. Strings must have the name of a variable defined previously for the data used in the plot. When a dictionary is provided, it is used as a mapping between a variable name and the unit to be used when plotting. ClimateGraph handles the unit transform.
  - **domains**: a list of domain names, referencing domains defined in the domain block.
  #### Miscelaneous parameters
  - filename: filename for the plot being described, note that should only be set if the plot block only produces **ONE** plot. Otherwise it will overwrite the previously saved plots.
  - figsize: a tuple (Width, height) in inches.
  - format: file format to use.
  - layout: type of plot layout. Options are: 'constrained', 'compressed', 'tight', 'none', a matplotlib.LayoutEngine or None.
  - dpi: Resolution in dots per inch.
  - transparent: boolean flag that sets the transparency (works only for formats with alpha channel).

The parameters specific to each plot are as follows:
- **Spatial Overlay** (accepted type values: "spatial-overlay", "spatialoverlay", "so")
    - base: name of Base data item. Should be a spatially distributed type of topology like RegularGrid.
    - superposed: name of Superposed data item. Should be a semi-distributed type of topology like PointSurface or SatelliteSwath (not implemented yet).
    - time_interval: time interval to use for plot in "d/m/yyyy-d/m/yyyy" format, where day and month can also be double-digitted.
    - levels: integer value for the amount of levels used in the contourf (defaults to 10)
    - reduction_method: method for the reduction of other dimensions (time for example). Supports 'mean', 'min', 'max'.
    - crs: Coordinate Reference System. Managed with cartopy but currently only manages 'platecarree'.
    - coastlines: boolean flag for adding coastlines to the plot.
    - borders: boolean flag for adding political borders to the plot.
    - cmap: colormap used for plotting.
    - bbox: optional [lon_min, lat_min, lon_max, lat_max] map extent; defaults to the intersection of the two datasets' bounds.
    - padding: fraction of each axis span added as a margin when the extent is computed automatically (i.e. when `bbox` is not set), so edge points aren't clipped (defaults to 0.05). A single point falls back to a fixed 0.5° margin.
    - drop_nans: boolean flag; when true, point stations whose reduced observation is NaN are dropped so they neither draw nor stretch the auto extent (defaults to false).

- **Spatial Map** (accepted type values: "spatial-map", "spatialmap", "map", "sm")

    A single-dataset map: it renders the chosen variable on top of a map. The rendering style is picked from the dataset topology — a filled contour (`contourf`) for spatially distributed data (`RegularGrid`), or a coloured scatter of points for in-situ data (`PointSurface` and other topologies). It is, in essence, one half of Spatial Overlay applied to a single dataset.
    - data: name of the data item to plot (the only dataset this plot takes).
    - time_interval: time interval to use for plot in "d/m/yyyy-d/m/yyyy" format, where day and month can also be double-digitted.
    - levels: integer value for the amount of levels used in the contourf, only used for `RegularGrid` data (defaults to 10).
    - markersize: marker area for the scatter, only used for point-like data (defaults to 40).
    - reduction_method: method for the reduction of other dimensions (time for example). Supports 'mean', 'min', 'max'.
    - crs: Coordinate Reference System. Managed with cartopy but currently only manages 'platecarree'.
    - coastlines: boolean flag for adding coastlines to the plot.
    - borders: boolean flag for adding political borders to the plot.
    - cmap: colormap used for plotting.
    - bbox: optional [lon_min, lat_min, lon_max, lat_max] map extent; defaults to the data's own bounds.
    - padding: fraction of each axis span added as a margin when the extent is computed automatically (i.e. when `bbox` is not set), so edge points aren't clipped (defaults to 0.05). A single point falls back to a fixed 0.5° margin.
    - drop_nans: boolean flag; for point data, stations whose reduced observation is NaN are dropped so they neither draw nor stretch the auto extent (defaults to false). Has no effect on the `RegularGrid` contourf path.

- **Timeseries** (accepted type values: "timeseries", "ts", "time-series")
    - base: name of a data item. The "other_data" will be resampled to the "base" geometry.
    - other_data: name or list of names of other data items.
    - radius_of_influence: radius of influence for resampling with Nearest Neighbor
    - time_interval: time interval to use for plot in "d/m/yyyy-d/m/yyyy" format, where day and month can also be double-digitted.
    - timestep: timestep used to resample time.
    - reduction_method: method used for reducing to 1D. Supports 'mean', 'min', 'max'.

- **Scatter** (accepted type values: "scatter", "sc")
    - base: name of a data item. The "other" will be resampled to the "base" geometry.
    - other: name of a data item.
    - radius_of_influence: radius of influence for resampling with Nearest Neighbor
    - time_interval: time interval to use for plot in "d/m/yyyy-d/m/yyyy" format, where day and month can also be double-digitted.
    - timestep: timestep used to resample time. Only worth using if dimension is "time"
    - dimension: For this plot data needs to be 1D, so this string parameter allows you to change that dimension (defaults to "time").
    - reduction_method: method used for reducing to 1D. Supports 'mean', 'min', 'max'.

- **Time Cycle** (accepted type values: "timecycle", "time cycle", "cycle")
    - base: name of a data item; other_data is resampled to its geometry. Only the base draws a shaded ±1σ standard-deviation band; other_data is drawn as a line only.
    - other_data: name or list of names of other data items (lines only, no std band).
    - radius_of_influence: radius of influence for resampling with Nearest Neighbor.
    - time_interval: time interval in "d/m/yyyy-d/m/yyyy" format.
    - timestep: optional timestep to resample time before bucketing (must not be coarser than time_buckets).
    - time_buckets: cycle period to group by. Accepted values: "minute", "hour", "day", "season", "week", "quarter" (default "day"). The plot title reflects the chosen bucket.
    - reduction_method: reduces spatial dims before grouping. Supports 'mean', 'min', 'max'.

### ▶ Run

```bash
ClimateGraph run config.yaml
```

---

##  Example Configuration

```yaml
analysis:
  output_path:  "./test_data/results"
  debug: True

data:
  WRF_D02:
    path: "./test_data/wrf-20*.nc"
    topology: RegularGrid
    reader: wrf
    vars:
      Temperatura:
        name: T2
        unit: "kelvin"
      Presion:
        name: PSFC
        unit: "pascal"
  DMC:
    path: "./test_data/dmc*.nc"
    topology: PointSurface
    reader: DMC
    vars:
      Temperatura:
        name: temperatura
        unit: "degC"
      Presion:
        name: presionEstacion
        unit: "hectopascal"
domains:
  RM:
    type: attr
    field_name: region
    field_value:  13
  Litoral:
    type: attr
    field_name: zonaGeografica
    field_value: Litoral
  Poly1:
    type: polygon
    vertex: [[-73.51507, -33.43938],[-73.51507, -36.46943],[-69.68720, -36.46943],[-69.68720, -33.43938]]
plots:
  ts:
    type: timeseries
    base: "DMC"
    other_data: ["WRF_D02"]
    domains: ["RM", "Litoral"]
    time_interval: 1/1/2019-1/2/2019
    timestep: "D"
    radius_of_influence: 10000
    vars:
      Temperatura: kelvin
      Presion: pascal
  scatter:
    type: scatter
    base: "DMC"
    domains: ["Valle"]
    other: "WRF_D02"
    time_interval: 1/1/2019-1/2/2019
    timestep: "D"
    radius_of_influence: 10000
    dimension: time
    vars:
      Temperatura: kelvin
      Presion: pascal
  so:
    type: spatial-overlay
    base: WRF_D02
    superposed: DMC
    domains: ["Poly1"]
    vars:
      Temperatura: kelvin
      Presion: pascal
    time_interval: 1/1/2019-1/2/2019
    reduction_method: mean

```

---

##  Architecture Overview

---

## 🔌 Extending the Framework

###  Adding a New Plot

1. Create a config model:

```python
class MyPlotConfig(BaseModel):
    type: Literal["my-plot"]
    ...
```

2. Create the plot class:

```python
class MyPlot(Plot):
    aliases = ["my-plot"]
    config_model = MyPlotConfig

    def plot(self):
        ...
```

3. Done — it auto-registers.

** Keep in mind that extra parameters not defined in the PlotConfig will be available inside the MyPlot class as "self.plot_kwargs" **

---
###  Adding a New Data Reader

1. Create a reader class inside of one of the reader topology directories inheriting the Reader abstract class, and  a topology for it:

```python
class MyReader(Reader):
    topology = "PointSurface" or other topology type
    ...
```

2. Override the open_mfdataset class method:

```python
class MyReader(Reader):
    ...
    @classmethod
    def open_mfdataset(
        cls, files: list[Path] | Path, vars: dict, **kwargs
    ) -> xr.Dataset:
    ... reading logic ...
```

3. Done — it auto-registers and is now available for use as a reader in the configuration file.

** Keep in mind that the Reader abstract class open_mfdataset signature MUST be respected for it to work. Also the vars mapping should be used to rename the vars and drop all not needed vars **

---

---
###  Adding a New Domain

1. Create a reader class inside of one of the reader topology directories inheriting the Reader abstract class, and  a topology for it:

```python
###  Adding a New Plot

1. Create a config model:

```python
class MyDomainConfig(BaseModel):
    type: Literal["my-domain"]
    ...
```

2. Create the plot class and implement the apply method:

```python
class MyPlot(Plot):
    aliases = ["my-dom", "my-domain"]
    config_model = MyDomainConfig

    def apply(self):
        ...
```

3. Done — it auto-registers.

---
##  Resampling and Alignment

ClimateGraph includes a centralized alignment system:

- Temporal alignment (resampling to common timestep and time interval)
- Spatial compatibility (topology handling)

Plots request alignment — they don’t implement it.

---

##  Supported Topology Types

| Type          | Description              |
| ------------- | ------------------------ |
| Regular Grid  | WRF, NetCDF gridded data |
| Point Surface | DMC station observations |
| (Planned)     | Satellite swath          |

---

## 📌 Roadmap

- [ ] Move to a config file all (or almost all) hard-coded values.
- [ ] Formally define the internal format for future reader developers.
- [ ] Statistical comparison module.
- [ ] Advanced regridding (xESMF).
- [ ] Interactive plots.

---

##  Known Limitations

- Limited automatic spatial interpolation (work in progress)
- CRS handling still being developed

---

## 🛠 Dependencies

- `numpy`
- `xarray`
- `netcdf4`
- `pyyaml`
- `pyresample`
- `pint`
- `pint_xarray`
- `matplotlib`
- `cartopy`
- `pydantic`
- `typer`
- `geopandas`
- `regionmask`
- `h5netcdf`
---

## Optional dependencies
- `ruff` (lint + format)
- `pre-commit` (git hook runner)
- `pytest`, `pytest-cov`, `pillow` (test suite + coverage + figure regression)

---

## Development

Contributing to ClimateGraph? The dev loop is:

```bash
git clone https://github.com/AntonioTorga/ClimateGraph.git
cd ClimateGraph

# Editable install with dev + test extras
pip install -e .[dev,test]

# One-time per clone: register the pre-commit git hook
pre-commit install
```

From there, every `git commit` automatically runs the lint, format, and small file
hooks. To trigger the same checks manually:

```bash
pre-commit run --all-files
```

Common tasks:

```bash
ruff check .                  # lint
ruff check --fix .            # lint and auto-fix what's safe
ruff format .                 # format
pytest -m "not slow"          # fast unit suite (~11 s)
pytest                        # full suite including integration + figure regression
pytest --cov                  # with coverage report
```

The integration suite under `tests/test_integration/` compares produced plots
to baselines in `tests/baseline_images/` via per-pixel RMS. To refresh the
baselines after an intentional plot change:

```bash
CLIMATEGRAPH_UPDATE_BASELINES=1 pytest tests/test_integration/
```

### CI

Every push and every PR targeting `main` or `develop` triggers
[`.github/workflows/ci.yml`](.github/workflows/ci.yml). The pipeline runs on
Python 3.12 and 3.13 in parallel; lint, fast tests, and a coverage gate
(`--cov-fail-under=85`) must all pass. Slow tests (NetCDF-touching + figure
regression) are not run in CI — they auto-skip when the sample data isn't
present on the runner.

---
### Financed by ANID Chile
This project is funded by ANID (Agencia Nacional de Investigación y Desarrollo) Chile through the FONDECYT Regular project N° 1231717
