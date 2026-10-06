"""Tests for the optional ``save_to`` finalize step on Reader.

``save_to`` (set in the data block, surfaced via ``spec.extras``) writes the
fully-finalized dataset to an exact NetCDF file path. It runs as the last step
of ``_finalize`` for every reader, and is a no-op when unset.
"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from ClimateGraph.reader.reader.reader import Reader, ReadSpec


def _ds() -> xr.Dataset:
    return xr.Dataset({"v": ("x", np.arange(3.0))})


class TestSave:
    def test_no_save_to_is_noop(self):
        ds = _ds()
        out = Reader._save(ds, ReadSpec(paths=[]))
        assert out is ds

    def test_writes_exact_file_path(self, tmp_path):
        target = tmp_path / "out.nc"
        spec = ReadSpec(paths=[], extras={"save_to": target})
        out = Reader._save(_ds(), spec)

        assert target.exists()
        assert out is not None
        with xr.open_dataset(target) as written:
            assert np.array_equal(written["v"].values, [0.0, 1.0, 2.0])

    def test_creates_missing_parent_dirs(self, tmp_path):
        target = tmp_path / "nested" / "deeper" / "out.nc"
        spec = ReadSpec(paths=[], extras={"save_to": target})
        Reader._save(_ds(), spec)
        assert target.exists()

    def test_directory_target_raises(self, tmp_path):
        spec = ReadSpec(paths=[], extras={"save_to": tmp_path})
        with pytest.raises(ValueError, match="exact NetCDF file path"):
            Reader._save(_ds(), spec)

    def test_non_netcdf_suffix_raises(self, tmp_path):
        spec = ReadSpec(paths=[], extras={"save_to": tmp_path / "out.txt"})
        with pytest.raises(ValueError, match="exact NetCDF file path"):
            Reader._save(_ds(), spec)
