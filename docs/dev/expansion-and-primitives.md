# Expansion, decorators and four new primitives

A working document: what changed in this session, why each piece is shaped the
way it is, and what was deliberately left alone. Not published with the Sphinx
site — `docs/dev/` sits outside `docs/source/`. The durable parts belong in the
architecture pages eventually; this is the rationale behind them.

---

## 0. State

```bash
pytest -m "not slow"          # 375 passing (305 at the start of the session)
ruff check ClimateGraph tests # clean
```

**New files**

| File | What |
|---|---|
| `ClimateGraph/plot/decorator.py` | The `Decorator` ABC |
| `ClimateGraph/plot/decorators.py` | `HLine`, `VLine`, `_reference_value` |
| `tests/test_plot/test_decorators.py` | 38 tests |
| `docs/examples/configs/{raster-contour,arrows,gradient,reference-lines}.yaml` | Four runnable examples |

**Modified**: `plot/plots.py`, `plot/primitive.py`, `plot/primitives.py`,
`utils/control_model.py`, `utils/general_utils.py`, `utils/registry.py`,
`docs/examples/_synthetic.py`, three test files, and the two example NetCDFs
(wind variables added — `model.nc` 711 KB → 735 KB, `stations.nc` 20 KB → 29 KB).

**Not mine**: `.gitignore` and `test_data/configs/minimal_single.yaml` were
already modified when the session started.

**Untracked and probably should be ignored**: `docs/examples/output/` — where
the example configs write their figures.

---

## 1. What you asked for, and what it turned into

You asked for four primitives: arrows, decorative lines, unfilled contours, and
raw 2-D display. Plus a windrose, which you reasoned had to be a primitive
because it needs a different kind of axes.

Three of those reframed during planning, and one question opened something much
larger.

| You asked for | What was built | Why it changed |
|---|---|---|
| arrows | **two** primitives, `gradient` and `arrows` | You meant a gradient field; I had built toward wind components. Both are useful and they are genuinely different operations |
| "raw 2-D, image show" | `raster`, on `pcolormesh` | `imshow` cannot draw your main data source at all |
| decorative lines | a whole **second family**, `decorations:` | A line is not a primitive, and treating it as one needed two extension points that the split then deleted |
| windrose primitive | polar as a mode for the whole composition | Not built yet — see §7 |
| — | **`ExpandableModel` / `expand()`** | Fell out of "where should `at: [50, p95]` fan out?" |

That last row is the important one and it is where most of the thinking went.

---

## 2. Expansion

### The question that started it

You wanted `at: [5, max, argmin]` on a reference line. I proposed a small
`expand_positions` helper. You pushed back twice: first that a `Line` object
should be *one* line and the fan-out belongs at parse time, then that the
project already had several of these and they should perhaps collapse.

So I surveyed. You were right, and it was worse than four places.

### What the survey found

**Six hand-written fan-outs that do not know about each other:**

1. `Plot.iterate_contexts` ([plot.py:218](../../ClimateGraph/plot/plot.py#L218))
   is a time × domain × var product whose docstring claims it "centralizes the
   nesting duplicated across the plot classes". **It has exactly one caller**,
   `Custom.plot`. The refactor it describes was written and then only wired
   into the newest plot type.
2. Five verbatim copies of
   `for t in normalize_time(self.plot_config.time): self._plot_one(t)`.
3. `SpatialOverlay` ([plots.py:419](../../ClimateGraph/plot/plots.py#L419)) and
   `SpatialMap` ([plots.py:606](../../ClimateGraph/plot/plots.py#L606))
   re-implement `resolve_domains` inline.
4. Six near-identical filename preambles and f-strings.
5. `_expand_domains` ([parser.py:84](../../ClimateGraph/utils/parser.py#L84)) —
   the one real config-time expansion.
6. Five *different* scalar→list widening predicates, and four different
   name-minting formats.

**The structural insight:** `one_for_each` and the runtime domain loop are *the
same axis at two moments*. The parser's `rewrite_map`
([parser.py:220](../../ClimateGraph/utils/parser.py#L220)) splices expanded
domain names straight into `plot_model.domains`, which is exactly the list
`resolve_domains` then filters. Config-time expansion is already a *producer*
for a runtime fan-out axis. They were never two concepts.

**Two live bugs fell out**, both consequences of writing fan-out six times:

- **`filename:` collides across every axis.** It is a static string, and all
  six sites do `auto_name if config.filename is None else config.filename`.
  Set it on a plot that fans out N ways and N figures are written to one path —
  only the last survives. `title` gets `.format(domain=, var=)` templating
  ([plots.py:1047](../../ClimateGraph/plot/plots.py#L1047)); `filename` does not.
- **Sub-day windows overwrite each other.** The filename stamp is `%d-%m-%Y`,
  so two hourly windows on the same day produce the same name.

Neither is fixed yet. Both are fixed for free by the migration in §7.

### What is *not* expansion

This mattered as much as what is. A path glob fans one `path:` out to many
files and `_join` folds them back into **one** dataset. `dim_reduce` walks
several dims and returns one object. `xticks`, `_apply_operations`,
`build_config_union` — same shape. They fan out and converge. They produce no
siblings, so they stay exactly where they are.

The unifiable set is precisely **one declaration → N sibling outputs**.

### The mechanism

`ExpandableModel` and `expand()`, in
[general_utils.py](../../ClimateGraph/utils/general_utils.py) (you chose that
over a separate `expansion.py`, next to the `normalize_time` it supersedes).

```python
class ExpandableModel(BaseModel):
    expands: ClassVar[tuple[str, ...]] = ()

    def expansion_values(self, field) -> list: ...   # hook 1
    @staticmethod
    def expansion_token(value): ...                   # naming
    def expansion_gate(self, field) -> bool: ...      # hook 2


def expand(model) -> list[tuple[dict, ExpandableModel]]:
    axes = [f for f in model.expands if model.expansion_gate(f)]
    if not axes:
        return [({}, model)]
    ...itertools.product over expansion_values(f) for each axis...
```

Fifteen lines of logic. It returns `(slots, copy)` pairs: `copy` is a
`model_copy` with each axis pinned to one value, `slots` maps each axis to that
value's *name* for filenames and labels.

### Why two hooks and not zero

They exist because two real cases are not "the list in that field":

- **`expansion_gate`** — `AttributeConfig.field_value: [a, b]` is genuinely
  ambiguous. With `one_for_each: false` it means "match any of these" (see
  `Attribute._filter`, [domains.py:62](../../ClimateGraph/domain/domains.py#L62));
  with it true, one domain per value. The gate turns that from special-case
  parser code into a declaration on the config.
- **`expansion_values`** — `PointsConfig` fans over point names from
  `resolve_points()`, which is not a declared list at all. Without the hook
  that needs a second code path.

### The design argument you won

My first version had an expanded copy keep its field's container shape —
`domains=["centro"]` rather than `domains="centro"`. You asked whether I was
cheating, and I was. The one-element list existed so `for dom in cfg.domains:`
downstream would keep running. The loop survives, the type still says "many",
and nothing downstream knows expansion happened — the fan-out ends up in two
places at once.

So: **an expanded copy holds a single value, and downstream has no loop left to
run.** The consequence is that `BasePlotConfig.domains` has to widen from
`list[str]` to `str | list[str]` — exactly how `time` is already declared. That
is part of §7, not done yet.

One exception, for a different reason: a `vars: {PM25: "ug/m**3"}` mapping
expands into **one-entry dicts**, not bare keys. Not to preserve shape so a
loop survives — because the dict is a name-to-unit map and the unit has
nowhere else to live. `expansion_token` recovers `"PM25"` for labelling. A nice
side effect is that this kills the five different spellings of
`vars[var] if isinstance(vars, dict) else None` scattered across the plot
classes.

### What currently uses it

Only decorations. `expands = ("at",)` on `LineConfig`
([decorators.py](../../ClimateGraph/plot/decorators.py)), expanded at render
time in `Custom._decorate`. That was deliberate sequencing: build the mechanism
first, adopt it somewhere new and low-risk, migrate the six existing sites
afterwards behind green tests.

---

## 3. Decorators — why a second family

### The argument

You said a reference line felt like decor, not a plot layer. That is right, and
here is the sharp version of why.

- A **primitive** draws data and participates in the figure's scales: it sets
  the data limits, it can own the colorbar, it defines what the axes show.
- A **decorator** annotates axes the primitives already established. It never
  extends the limits, never owns a colorbar, and must draw *after* every
  primitive so it lands on top.

Ordering is a real consequence, not a detail — everything used to be one loop
in declaration order, so a line declared first would be painted under a
`contourf`.

### The evidence that the split was right

An earlier draft bolted two extension points onto `Primitive` to make lines
work: `needs_data(cfg)` (a literal `at: 50` reads nothing, but
`SubplotConfig.dataset` is required) and `self_reduces` (`at: p95` needs the
distribution, but the orchestrator blanket-reduces to a scalar first).

**Giving decorators their own family deleted both.** `dataset` is simply
optional on `DecorationConfig`, because decorators as a family do not require
data. The unreduced array is simply how the family works, because reducing to a
single value is what a decorator *does*. And `check_var_scope` never had to
learn about them, because decorations are not subplots.

When a split removes the special cases you needed to avoid it, the split was
the right shape.

### How it works

| | `Primitive` | `Decorator` |
|---|---|---|
| block | `subplots:` | `decorations:` |
| `dataset` | required | **optional** |
| data handed over | blanket-reduced to the x/y axes | **unreduced** |
| colorbar | may own it | never |
| draw order | first, declaration order | second pass, after all primitives |
| hook | `render(ax, data, *, x, y, label)` | `draw(ax, data)` |

The second pass is `Custom._decorate` in
[plots.py](../../ClimateGraph/plot/plots.py). It expands each block, prepares
data only when a `dataset` is named, and formats the label against the slot —
so `label: "Observado {at}"` with `at: [mean, p95]` gives two distinct legend
entries from one block. That reuses the `.format()` idiom already in
`test_data/configs/showcase_points.yaml:66` for titles.

`_reference_value` resolves a position: a number passes through, a
`ReferenceEnum` becomes `np.nanmean`/`np.nanpercentile`/…, and anything else is
a date parsed by the existing `manage_time_interval` so `at: "15/6/2021"` is
dayfirst like every other date in a control file. `argmax`/`argmin` return the
*coordinate* at the extreme, which is what a vline wants.

### A wart worth knowing

A `vline` at `argmax` over a `(time, site)` dataset needs an explicit
`dim_reduce: {site: mean}`, because the decoration gets unreduced data and
`argmax` needs a series. That duplicates what the subplot does implicitly via
`reduction_method`. The fix would be giving `DecorationConfig` its own optional
`reduction_method`. Not done — your call.

---

## 4. The four new primitives

### `contour` — unfilled lines

A mirror of `ContourFill` on `data.plot.contour`. **Single-coloured by your
decision**, so `wants_colorbar = False`: the lines carry their values on inline
`ax.clabel` labels, which leaves the figure's one colour scale to whatever is
underneath.

### `raster` — the raw field

On `pcolormesh`, not `imshow`. The deciding fact is in your own data model:
`RegularGrid` carries **2-D curvilinear** `latitude`/`longitude` over `(y, x)` —
WRF and CHIMERE on Lambert have latitude varying with `x`. Verified empirically:

```
contour      OK -> QuadContourSet
pcolormesh   OK -> QuadMesh
imshow       FAIL ValueError: imshow requires 1D coordinates,
                  try using pcolormesh or contour(f)
```

`imshow` cannot draw your main data source at all, and on grids where it *can*
run it ignores the coordinate values and renders uneven spacing as if even —
the bad kind of failure. `pcolor` is legacy: same semantics, a patch per cell,
much slower.

**A bug this caught:** `RasterConfig` originally had a `shading` field.
`shading: nearest` blew up with
`Dimensions of C (22, 30) are incompatible with X (31) and/or Y (23)`. xarray's
`pcolormesh` **already infers cell edges** from the centres, so naming a
shading mode fights that inference instead of configuring it. The field is
gone; `extra="allow"` still carries `shading:` through for anyone wanting
`gouraud`. This only surfaced because the example configs were actually run —
the unit tests would not have caught it.

### `gradient` — what you actually meant

One variable. It differentiates the field already being drawn, so the arrows
point up the slope of the concentration itself. **No `required_vars`** — it is
an ordinary single-variable primitive.

The interesting part is spacing. A gradient needs the physical distance between
adjacent cells, and `np.gradient(f)` assumes 1 per index step.

- **1-D coordinates**: `np.gradient(f, yv, xv)` works, giving `[f]` per
  *degree* — still anisotropic, since a degree of longitude shrinks with
  latitude.
- **2-D curvilinear**: `np.gradient` cannot take them at all. There is no
  single "spacing along x" because it varies cell by cell.

I initially claimed index space at least gets the *direction* right. **It does
not**, unless cells are square: with cells 10 km wide and 1 km tall, a field
rising equally per index step in both directions is physically ten times
steeper in y, so the normalized arrow points diagonally when it should point
nearly straight up.

So `_step_metres` reads the spacing off the coordinates, cell by cell, with the
equirectangular approximation that holds at grid scale:

```python
dlon_dy, dlon_dx = np.gradient(lon)
dlat_dy, dlat_dx = np.gradient(lat)
coslat = np.cos(np.deg2rad(lat))
ex = R * np.deg2rad(np.hypot(dlon_dx * coslat, dlat_dx))   # metres per x step
ey = R * np.deg2rad(np.hypot(dlon_dy * coslat, dlat_dy))
```

Tested against known values: 111 km per degree of latitude, and longitude
spacing shrinking by exactly `cos(lat)`.

**Known limitation:** the result is *along-grid*, not true east/north. On a
rotated or Lambert grid the array axes are tilted relative to the meridians,
and this does not correct for it — a few degrees over a regional domain.
Correcting it needs the local grid rotation angle; we decided to leave it.

### `arrows` — a vector field from two variables

The usual figure is a concentration field with wind over it, so transport is
visible. Models write components (`u10`/`v10`); station networks report speed
and direction. `ArrowsConfig` takes either complete pair, never both, never
half of one.

Speed/direction converts with the **meteorological convention** — direction is
where the wind blows *from*, so the vector points the opposite way:
`u = -speed·sin(θ)`, `v = -speed·cos(θ)`.

**Single-coloured by your decision**: an arrow already carries its magnitude in
its length.

### The multi-variable extension, and the shape debate

`arrows` is the first primitive needing more than one variable, which
`SubplotConfig` could not express. Three shapes were on the table:

1. `data` becomes a Dataset keyed by role
2. `data` stays an array, roles come as a separate `roles=` kwarg
3. (rejected early) a per-class `var_roles` ClassVar

You asked the deciding question: *where does the mess live?*

- **Dataset**: two places. `Arrows.render` indexes `data["u"]`, and
  `_prepare_subplot_data` gets one branch. The five existing primitives are
  untouched.
- **`roles=` kwarg**: seven places. An unused parameter on every single-var
  primitive, plus the same branch, plus the call site.

And on extensibility: with the Dataset, a future primitive needing a third or
fourth variable declares it in `required_vars` and reads it by role — **no new
parameter, ever**.

What makes the union safe rather than sloppy: **which form you get is fixed by
your own class, not by the data.** A primitive declaring `required_vars` always
gets a Dataset; one that does not always gets an array. No `render` ever writes
an `isinstance` check. That invariant is stated in the ABC's docstring.

`required_vars` is a **classmethod taking the config**, not a ClassVar, because
`arrows` accepts two spellings and the answer depends on what was written.

---

## 5. The registry fix

`Line` — the shared styling base between `Decorator` and `HLine`/`VLine` — was
registering itself as `type: line`, an abstract class addressable by name from
a control file.

My first fix made `Line` a plain non-`Decorator` mixin. You rejected it: *"a fix
should go into the registry not bypass the abstraction layer."* Correct — the
real statement is "a class you cannot instantiate should not be addressable",
and that belongs in `RegistryMixin`.

Two things made it safe:

1. **Nothing else breaks.** A survey of every registry found `line` was the
   *only* abstract entry across Plot (16), Primitive (7), Decorator (5), Domain
   (9) and Data (8).
2. **`inspect.isabstract` works inside `__init_subclass__`**, which is
   surprising — `ABCMeta` has not set `__abstractmethods__` at that point. The
   stdlib handles exactly this case by falling back to scanning the class dict
   and bases. Verified before relying on it; the comment in
   [registry.py](../../ClimateGraph/utils/registry.py) records why.

**Also found:** `Reader` does not use `RegistryMixin` at all. It has its own
two-level `registry` (`dict[topology, dict[name, class]]`), its own
`__init_subclass__`, and `type_aliases` instead of `aliases` —
[reader.py:72-89](../../ClimateGraph/reader/reader/reader.py#L72-L89). A
parallel reimplementation of the same idea. You said to handle it later; it is
already a roadmap item.

---

## 6. Open questions you should decide

1. **`DecorationConfig.reduction_method`** — fixes the `argmax` wart in §3.
2. **Along-grid vs true-north arrows** — §4; ~10 more lines if you want it.
3. **`docs/examples/output/`** should probably be gitignored.
4. **The example NetCDFs grew** with the wind variables. Still small, but they
   are tracked, so it is a real repository decision.

---

## 7. What is not done

**A4 — polar axes and the windrose.** Untouched, and you asked me to explain it
in more detail before writing it. The design: polar is a property of the
*composition*, not a primitive. A `PolarAxes` consumes `(theta, r)` through the
same calls as a Cartesian one, so once `custom` can create a polar axes and
convert the coordinate bound to `x` into radians, *every existing primitive
becomes a rose for free* — a year wrapped into an annual rose is `series` with
theta = day-of-year. Only the binned windrose proper is a new drawing
operation. No new dependency: the `windrose` package is unpinned, lightly
maintained, and puts *frequency* on the radial axis rather than wind speed.

**B2 — migrate the plots onto `expand()`.** This deletes `iterate_contexts`,
the five duplicate `plot()` bodies and the two inlined `resolve_domains`, and
collapses the six filename f-strings into declared templates. It also fixes
both bugs in §2: `filename:` becomes a template (stem if plain, template if it
has braces — your decision), with enforced axis coverage so a name can never
collide; and the time stamp widens when a window is sub-day.

**This is the riskiest step in the whole plan** — it could silently rename
every output figure, including the committed examples. There is a
filename-snapshot regression gate specified for it in the plan file.

**B3 — migrate domains onto `expand()`.** `AttributeConfig.expands =
("field_value",)` with the gate; `PointsConfig` overrides `expansion_values`.
The `rewrite_map` has to stay: `check_plot_domain_refs` validates against
*pre-expansion* names, which is why `_expand_domains` runs after
`model_validate` in the first place.

**The `TimeBucketEnum` addendum.** Worse than it first looked.
`monthly = "quarter"` and `weekly = "week"` have names disagreeing with their
values, and `check_timestep_vs_bucket`
([plots.py:739](../../ClimateGraph/plot/plots.py#L739)) looks the bucket up in a
dict keyed by values that largely do not exist. `minute`, `week` and `quarter`
raise a bare `KeyError` out of config validation; `month` and `dayofyear` are
listed but unreachable; any timestep beyond hourly/daily/monthly raises too.
And `groupby("time.week")` no longer resolves on pandas 2 regardless.

**Docs.** None of this is in the Sphinx site yet: the primitives table is still
three rows, there is no decorators section, no expansion page, and the four new
examples are not in `examples.rst`.

---

## 8. The seams — how to extend it now

**A primitive** (`primitives.py`): a `SubplotConfig` subclass with a `type`
Literal, and a `Primitive` subclass with `config`, `aliases`,
`required_coords`, and `render`. It self-registers. Add `required_vars` if it
needs more than one variable, and it then receives a Dataset keyed by role.

**A decorator** (`decorators.py`): a `DecorationConfig` subclass and a
`Decorator` subclass with `draw(ax, data)`. `dataset` is optional for the
family. Add `expands` if a field should fan out.

**A new expansion axis**: add the field name to the config's `expands`. Override
`expansion_gate` if it needs a flag, `expansion_values` if the values come from
somewhere other than the field.

**Import ordering matters.** `primitives` and `decorators` are both imported
explicitly near the top of `plots.py`, *before* `build_config_union()` runs,
because `plot/__init__.py`'s pkgutil loop gives no ordering guarantee. A new
module of either family needs the same explicit import.

---

## 9. Found but not fixed

- `Primitive.required_coords` is declared on both the primitive class and its
  config, and **only the config copy is ever read** (by
  `SubplotConfig._check_required_coords`). The class-level copies are
  decorative. New primitives follow the existing convention rather than
  introduce a second style mid-stream.
- `ScatterConfig.data` is a plain `list[str]` with an exactly-two validator and
  no widening, while `TimeSeries`/`TimeCycle` widen theirs; `SpatialOverlay`
  uses `base`/`superposed` and `SpatialMap` a scalar `data`. Four spellings of
  "which datasets", papered over by `_DATASET_REF_FIELDS`.
- `AnalysisModel.workers` is read into the kernel and never parallelizes
  anything.
- `_wrap_single_data` is byte-identical in two classes
  ([plots.py:139](../../ClimateGraph/plot/plots.py#L139) and
  [plots.py:727](../../ClimateGraph/plot/plots.py#L727)); one
  `@field_validator("vars", "data", mode="before", check_fields=False)` on
  `BasePlotConfig` would replace all three widening validators. Superseded by
  B2 anyway.
