"""Chunking of the opened dataset.

Chunking happens before ``_preprocess``, so the dim names in play are the
file's own. A dim-keyed spec written in canonical names misses them silently
and xarray falls back to the file's internal layout — which for real model
output is often one timestep per chunk.
"""

import numpy as np
import pytest
import xarray as xr

from ClimateGraph.reader import Reader
from ClimateGraph.reader.reader.reader import ReadSpec

VARS = {"Temperatura": {"name": "T2", "unit": "kelvin"}}


def _write_chunked(path, n_time=6, n_y=4, n_x=5):
    """A grid file with wrfout's shape: a ``Time`` dim, chunked per timestep."""
    lat, lon = np.meshgrid(
        np.linspace(-36.0, -33.0, n_y), np.linspace(-73.0, -69.0, n_x), indexing="ij"
    )
    ds = xr.Dataset(
        {"T2": (("Time", "y", "x"), np.random.rand(n_time, n_y, n_x).astype("f4"))},
        coords={
            "latitude": (("y", "x"), lat),
            "longitude": (("y", "x"), lon),
        },
    )
    ds.to_netcdf(path, encoding={"T2": {"chunksizes": (1, 2, 2)}})
    return path


@pytest.fixture
def chunked_file(tmp_path):
    return _write_chunked(tmp_path / "grid.nc")


def _read(path, extras=None):
    cls = Reader.get_reader_subclass("RegularGrid", "defaultgrid")
    return cls.read(ReadSpec(paths=[path], vars=VARS, extras=extras or {}))


class TestFixture:
    def test_file_is_chunked_per_timestep(self, chunked_file):
        # Without this the rest of the module proves nothing.
        raw = xr.open_dataset(chunked_file)
        assert raw["T2"].encoding["chunksizes"] == (1, 2, 2)

    def test_a_canonical_key_misses_the_native_dim(self, chunked_file):
        # The trap: the dim is `Time`, so a `time` key is dropped and every dim
        # falls back to the file's layout.
        missed = xr.open_dataset(chunked_file, chunks={"time": -1})
        assert missed["T2"].chunks == ((1,) * 6, (2, 2), (2, 2, 1))


class TestReaderChunking:
    def test_default_is_one_chunk_per_file(self, chunked_file):
        # A scalar applies whatever the dims are called.
        assert _read(chunked_file)["Temperatura"].chunks == ((6,), (4,), (5,))

    def test_geometry_dims_arrive_whole(self, chunked_file):
        # apply_ufunc rejects a split core dim, so the resample depends on this.
        chunks = _read(chunked_file)["Temperatura"].chunks
        assert chunks[1] == (4,) and chunks[2] == (5,)

    def test_chunks_extra_overrides_the_default(self, chunked_file):
        chunks = _read(chunked_file, extras={"chunks": {"Time": 2}})
        assert chunks["Temperatura"].chunks[0] == (2, 2, 2)

    def test_unsafe_path_chunks_the_same(self, chunked_file):
        cls = Reader.get_reader_subclass("RegularGrid", "defaultgrid")
        ds = cls.read(ReadSpec(paths=[chunked_file], vars=VARS, load_mode="unsafe"))
        assert ds["Temperatura"].chunks == ((6,), (4,), (5,))
