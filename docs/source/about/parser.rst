Configuration parsing
=====================

:mod:`ClimateGraph.utils.parser` — :mod:`ClimateGraph.utils.control_model`

Purpose
-------

Turning a control file into live objects happens in two modules. The pydantic check schema live in ``control_model.py``.
The reading and the construction live in ``parser.py``.

The result is the three registries the rest of the run works from: the datasets,
the domains and the plots, each keyed by the name chosen in the config.

The Parser
----------

:class:`~ClimateGraph.utils.parser.Parser` has two methods.

:meth:`~ClimateGraph.utils.parser.Parser.read_control` centralizes the file
formats. JSON, YAML and YML each have a loader; the method picks one by suffix
and returns a plain mapping. Everything downstream sees the same standardized
output regardless of which format was written.

:meth:`~ClimateGraph.utils.parser.Parser.parse_control` uses that as a
subroutine, validates the mapping against the Pydantic model, and then builds
the objects:

.. code-block:: text

   read_control(path)                 any supported format -> dict
        ↓
   ControlFile.model_validate(dict)   schema + cross-block checks
        ↓
   Data.create(...)      per data block
   Domain.create(...)    per domain block, after expansion
   Plot.create(...)      per plot block, handed the two registries above
        ↓
   analysis, data, plots, domains

A :class:`pydantic.ValidationError` is caught and re-raised as a ``ValueError``
that lists every problem with the offending input, rather than a stack trace.

The control file model
----------------------

:class:`~ClimateGraph.utils.control_model.ControlFile` is the top-level model and
composes the rest: ``analysis``, ``data``, ``domains`` and ``plots``. Block order
in the file does not matter, though starting with data definition and
ending with the plots is a more readable approach.

Each model carries the checks that belong to it to keep internal consistency.

Where the schema comes from
---------------------------

The plot and domain schemas are not written out in ``control_model.py``. They are
assembled at import time from the type registries. This allows the creation of new types
without having to mess with the Model. Allowing the new type inclusion work to be limited to
the new class.

Each concrete plot and domain declares its own config model next to its
implementation, registers itself, and those models are collected into a
discriminated union keyed on ``type``. So the definition of a valid
``type: timeseries`` block lives with ``Timeseries``, not here — and adding a new
plot type extends the config schema without touching this module. See
:doc:`registry`.

The checks that need to see more than one block sit on ``ControlFile`` and check domain and variable consistency
between the plots blocks and the domain and data variables declaration.


Reader keyword arguments
------------------------

``DataModel`` sets ``extra="allow"``, so any field it does not recognise is kept
and forwarded to the reader. That is how reader-specific options reach their
reader without ``Data`` or ``DataModel`` growing a parameter for each one.

``parse_control`` adds the declared lifecycle fields into the same bundle —
``load_mode``, ``cache_dir`` (defaulting to ``output_path/.cache``) and
``save_to`` — so the reader receives one complete set of keyword arguments.

Domain expansion
----------------

One domain block can become several domain instances.
:func:`~ClimateGraph.utils.parser._expansion_entries` computes the expansions for
a single block; :func:`~ClimateGraph.utils.parser._expand_domains` drives it over
all of them and returns the expanded mapping plus a rewrite map from each
original name to the names it became. ``parse_control`` applies that map to the
plots' domain references, so a plot pointing at the original block iterates over
all of its expansions.

This happens at parse time, so everything downstream sees a flat set of ordinary
domains and nothing else needs to know that fan-out exists.

Which blocks expand, and how the results are named, is covered in
:doc:`../reference/control-file`.

Points targets
--------------

:func:`~ClimateGraph.utils.parser._points_target` builds the in-memory
:class:`~ClimateGraph.data.PointSurface` that a points domain resamples onto,
letting a config declare the points to compare against rather than pointing at an
existing dataset. It is memoized on the resolved point set, so every expansion of
one block shares a single target object and therefore a single resample-cache
entry; a different point set gets a fresh target with its own name so geometries
cannot collide in that cache.

Keep in mind
------------

Unknown keys are an error in some blocks and silent in others
   ``analysis`` and ``vars`` forbid extras. ``data`` allows them on purpose, to
   forward reader options. Plot blocks allow them too, so they can reach
   matplotlib — which means a misspelled plot field is ignored rather than
   reported.
