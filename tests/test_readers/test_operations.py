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
import xarray as xr

from ClimateGraph.reader.reader.reader import Reader, ReadSpec


def _ds() -> xr.Dataset:
    return xr.Dataset({"PM25": ("time", [1.0, 2.0, 3.0])}, coords={"time": [0, 1, 2]})


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

    def test_missing_variable_is_skipped(self):
        ds = _ds()
        spec = ReadSpec(
            paths=[],
            vars={"Absent": {"name": "absent", "unit": "ppb", "operation": "*3"}},
        )
        out = Reader._apply_operations(ds, spec)
        xr.testing.assert_identical(out, ds)


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
