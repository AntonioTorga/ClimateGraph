# ClimateGraph — Usage & Config Reference

A fast, current reference for authoring ClimateGraph config files. This reflects the
config surface as of the latest changes (`data:` lists, resample-as-domain, `type: custom`
primitives, axis decoration). For architecture/extension internals, see `README.md`.

---

## Run

```bash
pip install -e ".[test]"          # editable install (dev/test extras)
ClimateGraph run path/to/config.yaml           # or a .json / .yml
ClimateGraph run path/to/config.yaml --debug   # verbose ClimateGraph logs
ClimateGraph version
```
`--debug` (or `debug: true` in the `analysis` block) raises **only** the ClimateGraph
logger to DEBUG — matplotlib/PIL stay quiet. The CLI flag wins over the config value.

Runnable examples live in `test_data/configs/` — start with
`template_custom_timeseries.yaml`, `showcase_resampling.yaml`, `showcase_composition.yaml`.

---

## Config skeleton

```yaml
analysis:                 # required
  output_path: "./results/run1"   # figures land in output_path/<plot_name>/
  debug: false            # optional
  workers: null           # optional dask workers

data:                     # required — one block per dataset
  DATASET_NAME: { ... }

domains:                  # optional — spatial filters / reprojections
  DOMAIN_NAME: { ... }

plots:                    # optional — what to render
  PLOT_NAME: { ... }
```
Names (`DATASET_NAME`, `DOMAIN_NAME`, `PLOT_NAME`) are your own handles; plots reference
datasets/domains by these names.

---

## `data` — datasets

```yaml
data:
  WRF:
    path: "./data/wrf-20*.nc"      # a glob, a single path, or a [list] of paths
    topology: RegularGrid          # RegularGrid (gridded) | PointSurface (stations)
    reader: wrf                    # see readers below (must match the topology)
    crs: platecarree               # optional (default platecarree)
    vars:                          # optional — see the three forms below
      Temperatura: {name: T2, unit: kelvin}
    # optional lifecycle knobs:
    save_to: "./data/wrf_processed.nc"   # write the loaded dataset to NetCDF
    metadata: "./data/stations.csv"      # reader-specific extra (e.g. station coords)
```

**Readers by topology** (canonical name → what it reads):
- `RegularGrid`: `wrf`, `chimere`
- `PointSurface`: `dmc`, `sinca` (NetCDF); `station-per-file` (one CSV per station),
  `single-file` (one CSV, all stations), `variable-per-file` (one CSV per variable).
  CSV readers usually need a `metadata:` file for station coordinates.

**`vars` — three forms:**
```yaml
vars: {NO2: {name: no2, unit: "ug/m**3"}}   # full: rename file var + declare unit
vars: [NO2, CO]                             # list: keep file-native names, no units
# (omit vars entirely)                      # keep every file variable, file-native names
```
- `unit` is a **pint** unit; enables conversion at plot time. Omit → no conversion.
- `operation` (in the full form) applies arithmetic at read time, e.g.
  `{name: CO, unit: ppm, operation: "/1000"}` or `"*2.62"` (a leading operator implies
  the variable, so `*2.62` means `var * 2.62`). Can also compose from other vars by name.

---

## `domains` — spatial filters (and optional reprojection)

A domain does an **optional reprojection** (`resample_to`) **then a filter**. A plot's
`domains: [a, b]` **fans out** — one output per domain (not a pipeline).

```yaml
domains:
  region13:                        # attribute filter
    type: attr                     # aliases: attribute
    field_name: region
    field_value: 13                # scalar; or a [list] -> keeps all matching (isin)
    # one_for_each: true           # if field_value is a list, expand into N domains,
                                   #   one per value (name__value); plots referencing
                                   #   this name iterate over all of them automatically

  metro:                           # polygon mask
    type: polygon                  # aliases: poly
    vertex: [[-73.5,-33.4],[-73.5,-36.5],[-69.7,-36.5],[-69.7,-33.4]]

  everything:
    type: all                      # no filter (explicit "use all data")

  from_shape:
    type: shapefile                # aliases: shp
    path: "./regions.shp"
    field_value: "Metropolitana"
```

**Reprojection (`resample_to`) — on ANY domain:**
```yaml
domains:
  model_at_stations:
    type: all                      # 'all' = pure reprojection, no filter
    resample_to: STATIONS          # sample the incoming dataset onto STATIONS' geometry
    radius_of_influence: 20000     # metres (default 50000)
    # engine: pyresample           # optional; engine_kwargs: {method: gaussian, ...}
  region13_at_stations:
    type: attr                     # reproject THEN filter: lets a model grid be filtered
    resample_to: STATIONS          #   by a *station* attribute (which only exists once
    field_name: region             #   the grid is sampled at the stations)
    field_value: 13
```
Applied to the target dataset itself, the reprojection short-circuits to identity.

---

## `plots`

Every plot supports these **common** fields (from `BasePlotConfig`):

| field | meaning |
|-------|---------|
| `vars` | `[list]` (keep native units) or `{var: unit}` (convert). One figure per var. |
| `time` | a date `"15/6/2021"`, a range `"1/6/2021 - 30/6/2021"`, or a **[list]** (fans out into one figure per entry). Dayfirst. |
| `domains` | `[names]` — one figure per domain (omit = whole dataset). |
| `dim_reduce` | per-dim selection/reduction before the main reduce (see below). |
| `grid` | axis reference lines — `true` / `12` / `{x: 12, y: ticks, offset: 0.5}`. |
| `xticks` / `yticks` | named ticks: `{0: "Surface", 5: "850 hPa"}`. |
| `filename` | override the auto-generated output name. |
| plus matplotlib passthroughs: `figsize`, `title`, `xlabel`, `ylabel`, `format`, `dpi`, `linewidth`, `color`, … |

### Plot types & their extra fields

```yaml
plots:
  # line(s) over time — one line per dataset in `data`, space reduced away
  ts:
    type: timeseries               # aliases: ts, time-series
    data: [STATIONS, MODEL]        # str or [list]
    time: "1/1/2019 - 1/2/2019"
    timestep: D                    # optional pre-resample: h, D, ME, Y, ...
    reduction_method: mean         # mean | min | max
    vars: {Temperatura: degC}

  # diurnal/seasonal cycle; first dataset in `data` gets the ± std band
  cycle:
    type: timecycle                # aliases: cycle, time cycle
    data: STATIONS
    time_buckets: hour             # minute | hour | day | week | season | quarter
    timestep: h
    vars: {PM25: "ug/m**3"}

  # value-vs-value scatter of exactly two datasets: data[0] = x, data[1] = y
  sc:
    type: scatter                  # aliases: sc
    data: [STATIONS, MODEL]        # exactly 2 (co-locate with a resample_to domain)
    dimension: time                # dim to keep/pair over
    vars: {NO2: ppb}

  # single-dataset map (grid -> contourf, points -> coloured scatter)
  map:
    type: spatial-map              # aliases: map, sm, spatialmap
    data: MODEL
    dim_reduce: {z: {method: isel, value: 0}}   # e.g. surface level
    cmap: viridis
    levels: 12
    vars: {PM25: "ug/m**3"}

  # grid field + station points on one map
  overlay:
    type: spatial-overlay          # aliases: so, spatialoverlay
    base: MODEL                    # RegularGrid (contourf)
    superposed: STATIONS           # PointSurface (scatter)
    drop_nans: true
    vars: {PM25: "ug/m**3"}
```

### `type: custom` — compose primitives on shared axes

Full axis freedom: pick which coordinate goes on `x`/`y`. Var scope is **mutually
exclusive** — EITHER set `vars` at the plot level (re-renders once per var, every subplot
sees it) OR give each subplot its own `var` (fixed composition). Never both.

```yaml
plots:
  custom_ts:
    type: custom
    time: "1/1/2019 - 1/2/2019"
    vars: {Temperatura: degC}      # plot-level var scope
    grid: true
    subplots:
      - type: series               # line along one dim. aliases: line. needs x.
        dataset: STATIONS
        x: time
        label: "Observations"
        color: black
      - type: series
        dataset: MODEL
        x: time
        label: "Model"
        color: tab:red

  cross_var:                       # per-subplot var scope (each subplot its own var+time)
    type: custom
    subplots:
      - {type: series, dataset: STATIONS, var: PM25, x: time, time: "6/2021", label: June}
      - {type: series, dataset: STATIONS, var: PM25, x: time, time: "7/2021", label: July}
```
Primitives: `series` (needs `x`), `contourf` (needs `x` and `y`; extra `levels`, `cmap`),
`points` (needs `x` and `y`; extra `markersize`, `cmap`, `edgecolor`, `drop_nans`).
Subplot fields: `dataset`, `var`, `x`, `y`, `time`, `dim_reduce`, `reduction_method`,
`unit`, `label`, plus styling passthroughs (`color`, `linewidth`, …). `x`/`y` name a
**coordinate** (may be 2-D, e.g. `longitude` over `(y, x)`); everything not on an axis is
reduced away.

---

## Cross-cutting concepts

**`dim_reduce`** — per-dimension selection/reduction, applied before the plot's blanket
reduce. Handy for picking a vertical level or a member:
```yaml
dim_reduce:
  z: {method: isel, value: 0}      # index-select surface level
  z: {method: sel, value: 850}     # label-select
  member: mean                     # or just a method name: mean | min | max
```

**Units & conversion** — `vars: {var: unit}` converts to that unit at plot time; a bare
`vars: [var]` keeps file-native units. For a multi-dataset comparison, use the dict form
so every line shares a y-axis. On `custom`, a subplot's `unit:` overrides the plot-level
unit.

**Fan-out (many outputs from one block)** — a `time:` list → one figure per window; a
`domains:` list → one figure per domain; `one_for_each: true` on an attribute domain →
one domain (hence one figure set) per value. These multiply.

**Co-located comparison** — timeseries/scatter reduce each dataset over *its own* space by
default (station-network mean vs whole-grid mean). To sample a model *at the stations*,
attach a `resample_to: STATIONS` domain to the plot.

**Time syntax** — dayfirst. A bare coarse date spans its bucket (`"6/2021"` = all June);
ranges use `-` or `to`. Filenames embed the resolved start/end.

---

## Gotchas

- **Scatter** needs `vars` as a `{var: unit}` map and exactly two datasets in `data`.
- **`grid: true`** draws one line per major tick; `grid: N` draws exactly N; `offset` is a
  fraction of the spacing (`0.5` = midway between ticks). Named ticks are skipped on map
  (GeoAxes) plots.
- **Extra keys are allowed** on plot blocks (they flow to matplotlib), so a typo in a
  field name is silently ignored rather than erroring — double-check spellings.
- Output figures go to `output_path/<plot_name>/`; `test_data/results/` is gitignored.