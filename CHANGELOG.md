# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
the project uses [semantic versioning](https://semver.org/spec/v2.0.0.html).
While the major version is `0`, the configuration surface and the Python API may
still change between releases.

## [0.4.1] — 2026-10-23

Both fixes below were found on the same run: a year of hourly WRF output
resampled onto three weather stations. Neither reproduces on test data, which
is written unchunked.

### Fixed

- Resampling a dataset onto another geometry failed with
  `ValueError: dimension y ... consists of multiple chunks, but is also a core
  dimension` whenever the source came from a chunked NetCDF4 file. xarray
  honours a file's internal chunk layout for any dimension the reader does not
  name, which splits the geometry dims; `resample_vars` now rechunks them whole
  before the resample. A WRF `wrfout` file chunked `(1, 83, 56)` splits both
  `y` and `x`.
- Readers opened every file one timestep at a time. The chunk spec was written
  `{"time": ...}`, but chunking runs before `_preprocess` renames the
  dimensions, so on a file whose time dimension is natively called something
  else — `Time`, in WRF output — the key matched nothing and xarray fell back
  to the file's internal layout for *every* dimension. A year of hourly output
  became 8,760 chunks per variable, each a separate read serialised behind
  libnetcdf's global lock. Readers now default to one chunk per file.
- `timestep:` passed the enum member to pandas rather than its value. pandas
  resolves common aliases from a cache that tolerates a `str` subclass and
  type-checks strictly otherwise, so this worked for some timesteps and raised
  `TypeError: Argument 'freq' has incorrect type` for others.
- `workers:` built `LocalCluster(n_workers=1, threads_per_worker=N)` — one
  process with N threads. libnetcdf is not thread-safe, so xarray serialises
  every read behind a lock held per process; those threads queued on it and
  read no faster than one. Setting `workers: 8` measured *slower* than leaving
  it unset, paying cluster startup for nothing. It now builds N worker
  processes with one thread each, which read in parallel: on a cold run,
  roughly 1.7x end to end and ~5x on the reads themselves. Peak memory rises
  with the worker count, since each holds its own chunks.
- `timestep: Y` and `timestep: Q` were not valid pandas frequencies at all.
  pandas 2.2 deprecated them in favour of the period-end spellings and 3.0
  removed them, so both raised regardless of the above. They are now `YE` and
  `QE`. Nothing depended on the old spellings, which could only ever fail.

### Added

- `chunks:` in a data block, passed through to the reader, for datasets where
  one chunk per file is too large — a big grid with a long per-file time axis.
  Keyed on the file's own dimension names, since it applies before renaming:

  ```yaml
  data:
    MODEL:
      path: "wrfout_d02_2017-*"
      reader: wrf
      chunks: {Time: 48}
  ```

- `Reader.default_chunks`, overridable per reader subclass.

## [0.4.0] — 2026-10-02

The first released version. Development started in October 2025; earlier version
numbers were never tagged or published.

This release is about making the project legible: a full documentation site, a
docstring pass over every module, and the fixes that turned up while writing it.

### Added

- **Documentation site** built with Sphinx and the Furo theme, covering:
  - an architecture section with a page per module — the CLI, the application
    kernel, configuration parsing, the class registries, the data abstraction,
    the read lifecycle, domains, plots, primitives and the shared utilities
  - an API reference generated from the source, with a page per module
  - a configuration reference rendered from `USAGE.md`
  - installation and quickstart guides
- A `docs` extra (`pip install -e ".[docs]"`) holding the documentation
  toolchain.
- A `docs` job in CI that builds the site with warnings treated as errors, so a
  broken cross-reference fails the build.
- A ReadTheDocs configuration, including the system packages cartopy and
  pyresample need in order for the documentation build to import the package.
- `ROADMAP.md`, tracking the documentation effort and a list of proposed
  improvements toward a 1.0 release.

### Fixed

- **Packaging: `ClimateGraph.domain` and `ClimateGraph.utils` were missing from
  the built distribution.** The package list was maintained by hand and had
  fallen behind, so an installed copy was incomplete. Package discovery is now
  automatic.
- `ClimateGraph version` reads the version from the package metadata instead of
  a hardcoded string that had to be kept in step with `pyproject.toml` by hand.
- Several docstrings contained markup that rendered incorrectly or broke the
  documentation build: an unterminated emphasis marker, an unterminated
  substitution reference, and a list that was silently swallowed.
- `Points._filter` was documented as doing nothing; it selects a single site
  when the domain is one of a fan-out expansion.

### Changed

- Docstrings across the package were normalized to numpydoc. Summaries no longer
  repeat the name of the thing they document, which rendered awkwardly in the
  generated API pages. Module-level docstrings were added throughout.
- `USAGE.md` is now tracked in the repository and is the single source of truth
  for the configuration reference, rendered into the documentation site rather
  than duplicated there.

### Removed

- The `colors` field on the timeseries and scatter plot configurations. It was
  accepted by the configuration schema and never implemented, so a control file
  setting it got no error and no effect. Per-series colouring remains available
  through the `color` passthrough.

### Internal

- `_drop_nan_points` was defined twice, identically, in two modules; there is now
  one definition.
