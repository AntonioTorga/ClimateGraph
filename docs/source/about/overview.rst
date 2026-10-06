Architecture overview
=====================

ClimateGraph turns a declarative control file into figures. The user describes what
data exists, how to subset it, and what to draw from it. The framework works out the
rest: which files to read, how to reconcile datasets that have different
shapes, and what to compute before drawing, and in what order to do so.


The idea
--------

Environmental data arrives in formats and layouts that have little in common: a
model writes a gridded NetCDF, one monitoring network writes a CSV per station,
another writes a CSV per variable. Comparing two of them normally means writing
code that knows about both.

ClimateGraph's answer is to put everything behind one abstraction and let
configuration, rather than code, express the analysis. A plot can say *draw a
line over this domain comparing X and Y* without knowing how X and Y are
structured, or that they are structured differently from each other.

The main abstraction node is **topology** — the shape of the thing the data
describes. A station network, a regular grid and a satellite swath behave
differently enough to be treated as separate things (topologies). Inside a topology type everything can be
made uniform, and the interactions *between* buckets are standardized once.

The pipeline
------------

.. code-block:: text

   ClimateGraph run config.yaml
        │
        ▼
   CLI            provides the entry points
        │
        ▼
   AppKernel      holds the registries and the run-scoped settings,
        │         dispatches the jobs
        ▼
   Parser         reads the file, validates it, builds the objects
        │
        ├──▶ Data      one per dataset — lazy, topology-aware
        │       └──▶ Reader      turns files into a Dataset, on first access
        │
        ├──▶ Domain    narrows a dataset: optional reprojection, then a filter
        │
        └──▶ Plot      reduces, draws, decorates, saves
                 └──▶ Primitive  one drawable layer, for composed figures

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Stage
     - Role
   * - :doc:`cli`
     - What the framework makes available. Deliberately thin for now.
   * - :doc:`appkernel`
     - Connects the modules by holding the registries of everything the parser built, and sets up the run-scoped settings. The main loop.
   * - :doc:`parser`
     - Centralizes the config file formats, validates against the schema, and constructs the objects.
   * - :doc:`registry`
     - Manages how a subclass becomes usable from a control file without anything outside it changing.
   * - :doc:`data`
     - The dataset abstraction. Lazy, and organised around topology.
   * - :doc:`reader`
     - The read lifecycle: a fixed sequence of hooks that subclasses plug into.
   * - :doc:`domain`
     - A subset of a dataset. Takes a ``Data`` and returns a new ``Data``.
   * - :doc:`plot`
     - The main app result. Fans out over specified time domains, spatial domains and variables.
   * - :doc:`primitives`
     - Drawable layers, composed on shared axes by a ``custom`` plot.
   * - :doc:`utils`
     - The shared toolbox: enums, time parsing, dataset transforms, resampling backends.

Extending it
------------

Five families of class register themselves by name. Adding a member means
writing a subclass — there is no registration call, no central list of types,
and no edit to the configuration schema, because the schema is assembled from
the registries at import time.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Subclass
     - To support
   * - ``Data``
     - a new data topology
   * - ``Reader``
     - a new format or file layout within an existing topology
   * - ``Domain``
     - a new way to subset data
   * - ``Plot``
     - a new figure type
   * - ``Primitive``
     - a new drawable layer for composed figures


Current known limitations
-------------------------

The dimensional model assumes **geometry is fixed and time is a dimension beside
it**. That holds for a grid and for a station network, and it is what makes
everything else general.

It does not hold for a satellite swath, whose spatial coordinates vary with
time — the geometry itself moves. ``SatelliteSwath`` therefore exists as a bucket
but cannot currently be used. Real coordinate-reference-system support belongs
with that same work; today ``crs`` accepts a single value.

Future work
-----------

What is known to be missing or wrong. ``ROADMAP.md`` in the repository has the
same list with the code references attached.

Bigger changes
^^^^^^^^^^^^^^

- Let geometry vary with time, so satellite swaths can be used at all. Real CRS
  support goes with it; today ``crs`` only accepts ``platecarree``. See
  `Current known limitations`_ above.
- Make primitives the main plotting engine and keep the named plot types as
  convenience wrappers over them.
- Sort out the tangle between resampling and domain handling.
- Add other job types. Analysis and statistics jobs alongside plotting,
  dispatched the same way.
- Precompute. Instead of every plot pulling data through the pipeline when it
  needs it, the kernel would work out what the whole run needs, compute and
  cache that up front, and let the jobs start against data that is already
  processed. The commented-out eager load in ``run`` is where this starts.

Smaller fixes
^^^^^^^^^^^^^

- Warn when a plot block carries a field nobody reads. A typo is silently
  ignored today, because extra keys are allowed so they can reach matplotlib.
- ``workers`` sets threads, not workers. Rename it or change what it does.
- Clean up the points target. It is bolted onto the side instead of being
  something the domain model accounts for.
- Give ``Reader`` the same registry mixin as everything else. It has its own
  only because its registry is two levels deep.
- Rename the safe and unsafe load modes. They are about who opens the files,
  not about safety.
- Flatten ``reader/reader/``.
- Configure logging before parsing, so ``--debug`` covers the parsing too.
- Stop creating directories while validating a config.
- Use autodiscovery in ``data/__init__.py`` like the other subpackages do.
- Clear the kernel's settings along with its registries when a run ends, or
  clear neither.


Modules
-------

.. toctree::
   :maxdepth: 1

   cli
   appkernel
   parser
   registry
   data
   reader
   domain
   plot
   primitives
   utils
