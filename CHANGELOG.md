# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
the project uses [semantic versioning](https://semver.org/spec/v2.0.0.html).
While the major version is `0`, the configuration surface and the Python API may
still change between releases.

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
