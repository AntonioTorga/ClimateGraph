"""Tests for the optional ``time_offset`` postprocess step on Reader.

``time_offset`` (hours, set in the data block, surfaced via ``spec.extras``)
shifts the ``time`` coordinate so a UTC dataset can be read on a local
schedule. It runs as a guaranteed final step in ``read()`` for every reader.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from ClimateGraph.reader.reader.reader import Reader, ReadSpec


def _timed_ds() -> xr.Dataset:
    times = pd.date_range("2019-01-01T00:00", periods=3, freq="h")
    return xr.Dataset({"v": ("time", [1, 2, 3])}, coords={"time": times})


class TestApplyTimeOffset:
    def test_negative_offset_shifts_back(self):
        spec = ReadSpec(paths=[], extras={"time_offset": -3})
        out = Reader._apply_time_offset(_timed_ds(), spec)
        assert out["time"].values[0] == np.datetime64("2018-12-31T21:00:00")

    def test_positive_offset_shifts_forward(self):
        spec = ReadSpec(paths=[], extras={"time_offset": 5})
        out = Reader._apply_time_offset(_timed_ds(), spec)
        assert out["time"].values[0] == np.datetime64("2019-01-01T05:00:00")

    def test_fractional_hours(self):
        spec = ReadSpec(paths=[], extras={"time_offset": 1.5})
        out = Reader._apply_time_offset(_timed_ds(), spec)
        assert out["time"].values[0] == np.datetime64("2019-01-01T01:30:00")

    def test_absent_key_is_noop(self):
        ds = _timed_ds()
        assert Reader._apply_time_offset(ds, ReadSpec(paths=[])) is ds

    def test_zero_offset_is_noop(self):
        ds = _timed_ds()
        out = Reader._apply_time_offset(
            ds, ReadSpec(paths=[], extras={"time_offset": 0})
        )
        assert out is ds

    def test_no_time_coord_is_noop(self):
        ds = xr.Dataset({"v": ("t", [1])}, coords={"t": [0]})
        out = Reader._apply_time_offset(
            ds, ReadSpec(paths=[], extras={"time_offset": 5})
        )
        assert out is ds


def test_read_applies_offset_end_to_end():
    """A full ``read()`` walk applies the offset after ``_postprocess``."""
    captured = _timed_ds()

    class _Offset(Reader):
        topology = f"_offset_{id(captured)}"

        @classmethod
        def _resolve_paths(cls, spec):
            return spec.paths

        @classmethod
        def _open_many(cls, paths, spec):
            return captured

    try:
        spec = ReadSpec(
            paths=[Path("a.nc")], load_mode="safe", extras={"time_offset": -3}
        )
        ds = _Offset.read(spec)
        assert ds["time"].values[0] == np.datetime64("2018-12-31T21:00:00")
    finally:
        Reader.registry.pop(_Offset.topology.lower(), None)
