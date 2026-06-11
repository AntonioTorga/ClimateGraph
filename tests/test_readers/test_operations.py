"""Tests for the optional per-variable ``operation`` finalization step.

A var block may carry ``operation`` (a small arithmetic expression, e.g.
``"*3"``) for unit conversions pint can't express. ``Reader._apply_operations``
applies it to the variable's values; the declared ``unit`` is the unit *after*
the operation. It runs inside ``_finalize`` as a guaranteed final step for
every reader, alongside ``_apply_time_offset``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from ClimateGraph.reader.reader.reader import Reader, ReadSpec


def _ds() -> xr.Dataset:
    return xr.Dataset({"PM25": ("time", [1.0, 2.0, 3.0])}, coords={"time": [0, 1, 2]})


def _ab() -> xr.Dataset:
    return xr.Dataset(
        {"A": ("time", [1.0, 2.0]), "B": ("time", [3.0, 4.0])},
        coords={"time": [0, 1]},
    )


class TestApplyOperations:
    def test_operation_applied_by_config_name(self):
        spec = ReadSpec(
            paths=[], vars={"PM25": {"name": "PM25", "unit": "ppb", "operation": "*3"}}
        )
        out = Reader._apply_operations(_ds(), spec)
        np.testing.assert_allclose(out["PM25"].values, [3.0, 6.0, 9.0])

    def test_operation_resolved_by_native_name(self):
        # Dataset still keyed by the file-native name; vars keyed by config name.
        ds = xr.Dataset({"pm25": ("time", [1.0, 2.0])}, coords={"time": [0, 1]})
        spec = ReadSpec(
            paths=[], vars={"PM25": {"name": "pm25", "unit": "ppb", "operation": "/2"}}
        )
        out = Reader._apply_operations(ds, spec)
        np.testing.assert_allclose(out["pm25"].values, [0.5, 1.0])

    def test_no_operation_key_is_noop(self):
        ds = _ds()
        spec = ReadSpec(paths=[], vars={"PM25": {"name": "PM25", "unit": "ppb"}})
        out = Reader._apply_operations(ds, spec)
        xr.testing.assert_identical(out, ds)

    def test_absent_vars_is_noop(self):
        ds = _ds()
        out = Reader._apply_operations(ds, ReadSpec(paths=[]))
        xr.testing.assert_identical(out, ds)

    def test_undefined_self_reference_raises(self):
        # "Absent" declares a self-transform ("*3" -> "x*3") but its own data
        # isn't in the dataset, so `x` is undefined -> error (no silent skip).
        ds = _ds()
        spec = ReadSpec(
            paths=[],
            vars={"Absent": {"name": "absent", "unit": "ppb", "operation": "*3"}},
        )
        with pytest.raises(ValueError, match="unknown variable"):
            Reader._apply_operations(ds, spec)


class TestComposedVariables:
    def test_compose_new_var_from_bases_by_name(self):
        spec = ReadSpec(
            paths=[],
            vars={
                "A": {"name": "A", "unit": None},
                "B": {"name": "B", "unit": None},
                "C": {"unit": None, "operation": "A + B"},
            },
        )
        out = Reader._apply_operations(_ab(), spec)
        np.testing.assert_allclose(out["C"].values, [4.0, 6.0])
        # base vars untouched
        np.testing.assert_allclose(out["A"].values, [1.0, 2.0])

    def test_self_reference_by_canonical_name(self):
        spec = ReadSpec(
            paths=[], vars={"PM25": {"name": "PM25", "operation": "PM25 * 3"}}
        )
        out = Reader._apply_operations(_ds(), spec)
        np.testing.assert_allclose(out["PM25"].values, [3.0, 6.0, 9.0])

    def test_reference_undefined_variable_raises(self):
        spec = ReadSpec(
            paths=[],
            vars={
                "A": {"name": "A", "unit": None},
                "C": {"unit": None, "operation": "A + Z"},
            },
        )
        with pytest.raises(ValueError, match="unknown variable 'Z'"):
            Reader._apply_operations(_ab(), spec)

    def test_reference_other_composed_variable_raises(self):
        # D is composed (has an operation), so it's not a base var and C may not
        # reference it -> error (avoids evaluation-order chains).
        spec = ReadSpec(
            paths=[],
            vars={
                "A": {"name": "A", "unit": None},
                "D": {"unit": None, "operation": "A * 2"},
                "C": {"unit": None, "operation": "D + 1"},
            },
        )
        with pytest.raises(ValueError, match="unknown variable 'D'"):
            Reader._apply_operations(_ab(), spec)


def test_read_applies_operation_end_to_end():
    """A full ``read()`` walk applies the operation via ``_finalize``."""
    captured = _ds()

    class _Op(Reader):
        topology = f"_op_{id(captured)}"

        @classmethod
        def _resolve_paths(cls, spec):
            return spec.paths

        @classmethod
        def _open_many(cls, paths, spec):
            return captured

    try:
        spec = ReadSpec(
            paths=[Path("a.nc")],
            load_mode="safe",
            vars={"PM25": {"name": "PM25", "unit": "ppb", "operation": "*3"}},
        )
        ds = _Op.read(spec)
        np.testing.assert_allclose(ds["PM25"].values, [3.0, 6.0, 9.0])
    finally:
        Reader.registry.pop(_Op.topology.lower(), None)
