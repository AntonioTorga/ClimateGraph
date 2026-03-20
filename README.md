# 🌍 ClimateGraph

**ClimateGraph** is a modular Python framework for reading, transforming, and visualizing climate and environmental data from multiple sources.

It is designed to be:

* 🔌 **Extensible** — easily add new data readers and plot types
* ⚙️ **Config-driven** — controlled via YAML files
* 🧠 **Lazy & efficient** — data is only loaded and processed when needed

---

## ✨ Features

### 📥 Data Readers

* **WRF (Weather Research and Forecasting)** model outputs (gridded data)
* **DMC network** (point surface observations)
* Designed for future support:

  * Unstructured grids
  * Satellite swath data
  * Additional NetCDF-based datasets

---

### 📊 Plot Types

* **Spatial Overlay**

  * Overlay points of data over spatially distributed data.
  * Uses contour maps + scatter overlays

* **Timeseries**

  * Compare temporal evolution across datasets
  * Supports spatial resampling and time resampling and alignment.

* **Scatter**

  * Dataset-to-dataset comparison
  * Useful for validation and bias analysis

---

### 🔄 Data Handling

* Lazy data loading
* Time resampling and alignment
* Spatial Resampling (Cartopy and Pyresample based)
* Unit conversion 

---

## 🚀 Installation

```bash
git clone https://github.com/AntonioTorga/ClimateGraph.git
cd ClimateGraph
pip install .
```

---

## 📁 Project Structure

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

## ⚙️ Usage

ClimateGraph is driven by a YAML or JSON **control file**, with three key parts:

#### Analysis
Configuration for overall execution. The managed parameters are as following:
    output_path: Relative or absolute path to directory in which to leave the results.
    debug: Boolean flag, turns on debug mode. Defaults to False (doesn't do much yet)
#### Data
    topology: PointSurface, RegularGrid or SatelliteSwath (the latter is not yet supported)
    reader: Specific reader for your data (WRF, Chimere, DMC, etc).
    path: Relative or absolute path or list of paths. Accepts and expands hotkeys (*,?)
    vars: Block of information about the vars about to plot. Includes the name of the variable in the files and the unit.
    crs: Coordinate Reference System. Managed by Cartopy, currently only PlateCarree is available. 
#### Plots
    Depends on each plot. Soon a detailed guide, but can be seen in utils/control_model.py how every plot has it's own accepted parameters.

### ▶ Run

```bash
ClimateGraph run config.yaml
```

---

## 📝 Example Configuration

```yaml
analysis:
  output_path:  "./test_data/results"
  debug: True

data:
  WRF_D02:
    path: "/home/ato/Escritorio/Trabajos/Melodies-Monet/ClimateGraph/TestData/data/wrf/wrf-d02-20*.nc"
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
    path: "/home/ato/Escritorio/Trabajos/Melodies-Monet/ClimateGraph/TestData/data/dmc/dmc-2019.nc"
    topology: PointSurface
    reader: DMC
    vars:
      Temperatura:
        name: temperatura
        unit: "degC"
      Presion:
        name: presionEstacion
        unit: "hectopascal"
plots:
  ts:
    type: timeseries
    base: "DMC"
    other_data: ["WRF_D02"]
    time_interval: 1/1/2019-1/2/2019
    timestep: "D"
    radius_of_influence: 10000
    vars: 
      Temperatura: kelvin
      Presion: pascal
```

---

## 🧩 Architecture Overview

---

## 🔌 Extending the Framework

### ➕ Adding a New Plot

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

3. Done — it auto-registers

---
### ➕ Adding a New Data Reader

Soon

## 🔄 Resampling & Alignment

ClimateGraph includes a centralized alignment system:

* Temporal alignment (resampling to common timestep and time interval)
* Spatial compatibility (topology handling)

Plots request alignment — they don’t implement it.

---

## 🧪 Supported Data Types

| Type          | Description              |
| ------------- | ------------------------ |
| Regular Grid  | WRF, NetCDF gridded data |
| Point Surface | DMC station observations |
| (Planned)     | Satellite swath          |

---

## ⚠️ Known Limitations

* Limited automatic spatial interpolation (work in progress)
* CRS handling still being developed
* No spatial domain limitation as of yet.

---

## 🛠 Dependencies

* `numpy`
* `xarray`
* `netcdf4`
* `pyyaml`
* `pyresample`
* `pint`
* `pint_xarray`
* `matplotlib`
* `cartopy`
* `pydantic`
* `typer`

---

## 📌 Roadmap

* [ ] Domain definition with polygons, maps (shapefiles) or attributes in the netcdf file
* [ ] Statistical comparison module
* [ ] Advanced regridding (xESMF)
* [ ] Interactive plots

---

## 🤝 Contributing

Contributions are welcome!

You can:

* Add new data readers
* Implement new plot types
* Improve alignment methods
* Fix bugs or improve docs

---

## 📄 License

MIT License

---

## 💡 Philosophy

ClimateGraph is built around a simple idea:

> Separate **data standarization**, **resampling**, and **analysis** so each can evolve independently.
