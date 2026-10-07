# 🌍 ClimateGraph

[![CI](https://github.com/AntonioTorga/ClimateGraph/actions/workflows/ci.yml/badge.svg)](https://github.com/AntonioTorga/ClimateGraph/actions/workflows/ci.yml)
[![Documentation](https://readthedocs.org/projects/climategraph/badge/?version=latest)](https://climategraph.readthedocs.io/en/latest/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**ClimateGraph** reads, transforms and visualizes climate and environmental data
from sources that have nothing in common — a gridded model output, a network of
monitoring stations, a folder of CSVs — and lets you compare them without
writing code for each one.

A single control file says what data exists, how to filter it, and what to draw.

![Hourly PM2.5 from a station network and a model](https://raw.githubusercontent.com/AntonioTorga/ClimateGraph/main/docs/source/_static/examples/timeseries.png)

```yaml
analysis:
  output_path: "./results"

data:
  STATIONS:
    path: "./data/stations.nc"
    topology: PointSurface
    reader: defaultpointsurface
    vars: {PM25: {name: pm25, unit: "ug/m**3"}}
  MODEL:
    path: "./data/model.nc"
    topology: RegularGrid
    reader: defaultgrid
    vars: {PM25: {name: pm25, unit: "ug/m**3"}}

plots:
  comparison:
    type: timeseries
    data: [STATIONS, MODEL]
    time: "1/6/2021 - 10/6/2021"
    vars: {PM25: "ug/m**3"}
```

```console
$ ClimateGraph run config.yaml
```

That simple config file creates the picture above comparing PM2.5 between monitoring stations and a model.

## Why

- **Topology agnostic** — grids and station networks are compared directly;
  resampling between them is a configuration option, not your problem.
- **Config-driven** — the analysis lives in YAML or JSON, not in a script.
- **Lazy** — nothing is read until it is actually needed.
- **Extensible** — a new reader, plot type or domain is one subclass. It
  registers itself and the configuration schema picks it up automatically.

## Install

Requires Python 3.12+. Some dependencies build against system libraries:

```console
$ sudo apt-get install -y libgeos-dev libproj-dev libhdf5-dev libnetcdf-dev
$ git clone https://github.com/AntonioTorga/ClimateGraph.git
$ cd ClimateGraph
$ pip install -e .
```

The sample NetCDFs under `test_data/data/` are Git LFS and excluded from clones
by default, so this is quick and the fast test suite runs without them.

## Documentation

**[climategraph.readthedocs.io](https://climategraph.readthedocs.io)**

| | |
|---|---|
| [Quickstart](https://climategraph.readthedocs.io/en/latest/getting-started/quickstart.html) | From a blank file to a figure |
| [Examples](https://climategraph.readthedocs.io/en/latest/examples.html) | One per plot type, each with the config that produced it |
| [Control file reference](https://climategraph.readthedocs.io/en/latest/reference/control-file.html) | Every field of every block |
| [Architecture](https://climategraph.readthedocs.io/en/latest/about/overview.html) | How it works, module by module, and how to extend it |
| [API reference](https://climategraph.readthedocs.io/en/latest/api/index.html) | Generated from the source |

Try the examples straight from a clone — the data is in the repository:

```console
$ python docs/examples/make_data.py
$ ClimateGraph run docs/examples/configs/timeseries.yaml
```

## Development

```console
$ pip install -e ".[dev,test,docs]"
$ pre-commit install          # once per clone
$ pytest -m "not slow"
$ make -C docs html
```

Every push and every pull request against `main` or `develop` runs lint, the
fast test suite on Python 3.12 and 3.13, a coverage gate, and a strict
documentation build. Slow tests touch the LFS sample data and skip automatically
when it is absent.

## Funding

This project is funded by ANID (Agencia Nacional de Investigación y Desarrollo)
Chile, through the FONDECYT Regular project N° 1231717, directed by Nicolas
Huneeus.

## License

MIT — see [LICENSE](LICENSE).
