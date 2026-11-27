from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from ClimateGraph.reader import Reader
from ClimateGraph.reader.reader.reader import ReadSpec
from ClimateGraph.reader.reader.regular_grid.wrf import Wrf

NY, NX = 3, 4


def _raw_wrfout(path: Path, start: str, hours: int = 24) -> Path:
    """Write a file shaped like real wrfout, as opposed to cleaned NetCDF.

    Two differences drive the reader's raw-input handling and neither is present
    in the bundled ``wrf-2019-*.nc`` samples, which is how they went unnoticed:
    there is no ``Time`` coordinate (the valid times live in ``XTIME``, leaving
    ``Time`` a bare dimension), and ``XLAT``/``XLONG`` are written once per
    output time, so they arrive 3-D even though the grid is static.
    """
    times = pd.date_range(start, periods=hours, freq="h")
    lat2d, lon2d = np.meshgrid(np.arange(NY), np.arange(NX), indexing="ij")
    dims = ("Time", "south_north", "west_east")
    tiled = (hours, 1, 1)
    ds = xr.Dataset(
        {"T2": (dims, np.full((hours, NY, NX), 280.0))},
        coords={
            "XTIME": ("Time", times),
            "XLAT": (dims, np.tile(lat2d, tiled).astype(float)),
            "XLONG": (dims, np.tile(lon2d, tiled).astype(float)),
        },
    )
    ds.to_netcdf(path)
    return path


def _clean_wrf(path: Path, start: str, hours: int = 24) -> Path:
    """The already-cleaned shape: indexed ``Time`` coordinate, 2-D lat/lon."""
    times = pd.date_range(start, periods=hours, freq="h")
    lat2d, lon2d = np.meshgrid(np.arange(NY), np.arange(NX), indexing="ij")
    ds = xr.Dataset(
        {"T2": (("Time", "south_north", "west_east"), np.full((hours, NY, NX), 280.0))},
        coords={
            "Time": times,
            "XLAT": (("south_north", "west_east"), lat2d.astype(float)),
            "XLONG": (("south_north", "west_east"), lon2d.astype(float)),
        },
    )
    ds.to_netcdf(path)
    return path


VARS = {"Temperatura": {"name": "T2", "unit": "kelvin"}}


def test_wrf_is_registered():
    class_reader = Reader.get_reader_subclass("RegularGrid", "WRF")
    assert class_reader == Wrf


@pytest.mark.slow
def test_wrf_read():
    class_reader = Reader.get_reader_subclass("RegularGrid", "WRF")
    spec = ReadSpec(
        paths=[
            Path("test_data/data/wrf-2019-01.nc"),
            Path("test_data/data/wrf-2019-02.nc"),
        ],
        vars={"Temperatura": {"name": "T2", "unit": "kelvin"}},
    )
    obj = class_reader.read(spec)
    assert isinstance(obj, xr.Dataset)
    assert all(x in obj.coords for x in ["latitude", "longitude"])
    assert all(x in obj.dims for x in ["time", "x", "y"])
    assert "Temperatura" in obj.data_vars


class TestRawWrfout:
    """Reading files straight out of WRF, rather than cleaned NetCDF."""

    def test_time_is_indexed(self, tmp_path):
        """`time` must end up an *index*, not a bare coordinate.

        Without one, `open_mfdataset` cannot order the files and dies with
        "Could not find any dimension coordinates to use to order the Dataset
        objects for concatenation" — so this also covers the multi-file case.
        """
        obj = Wrf.read(
            ReadSpec(
                paths=[
                    _raw_wrfout(tmp_path / "a.nc", "2026-07-29"),
                    _raw_wrfout(tmp_path / "b.nc", "2026-07-30"),
                ],
                vars=VARS,
            )
        )
        assert "time" in obj.indexes
        assert obj.sizes["time"] == 48
        assert obj.indexes["time"].is_monotonic_increasing
        # The index is usable for label selection, which every plot relies on.
        assert obj.sel(time=slice("2026-07-29", "2026-07-29")).sizes["time"] == 24

    def test_preprocess_reads_no_values(self, tmp_path):
        """``_preprocess`` must not materialise anything.

        It runs per file while ``open_mfdataset`` is still opening, so building
        the ``time`` index here would read ``XTIME`` from all 1825 files during
        the open phase. The index is built once in ``_postprocess`` instead.
        """
        path = _raw_wrfout(tmp_path / "a.nc", "2026-07-29")
        ds = xr.open_dataset(path, chunks=-1)
        ds = Wrf._preprocess(ds, ReadSpec(paths=[path], vars=VARS))

        assert "time" not in ds.indexes
        assert ds["time"].chunks is not None
        assert ds["Temperatura"].chunks is not None

    def test_paths_are_sorted_for_nested_combine(self, tmp_path):
        """Nested combine concats in path order, so the order must be sorted.

        ``by_coords`` aligned on the time index instead; raw wrfout has none
        until after the combine, and an unsorted glob would interleave days.
        """
        spec = ReadSpec(
            paths=[tmp_path / "b.nc", tmp_path / "a.nc"],
            vars=VARS,
        )
        _raw_wrfout(tmp_path / "a.nc", "2026-07-29")
        _raw_wrfout(tmp_path / "b.nc", "2026-07-30")

        assert Wrf.combine_kwargs["combine"] == "nested"
        assert [p.name for p in Wrf._resolve_paths(spec)] == ["a.nc", "b.nc"]

    @pytest.mark.slow
    def test_eager_open_under_a_client_matches_the_lazy_path(self, tmp_path):
        """The worker-per-file path must produce what `open_mfdataset` produces.

        It assembles the Dataset by hand from gathered layouts and futures, so
        nothing checks the dims, the time order or the lat/lon against the lazy
        path unless they are compared directly.
        """
        pytest.importorskip("distributed")
        from distributed import Client, LocalCluster

        paths = [
            _raw_wrfout(tmp_path / "a.nc", "2026-07-29"),
            _raw_wrfout(tmp_path / "b.nc", "2026-07-30"),
        ]
        lazy = Wrf.read(ReadSpec(paths=paths, vars=VARS))

        with LocalCluster(n_workers=2, threads_per_worker=1, processes=True) as cluster:
            with Client(cluster):
                eager = Wrf.read(ReadSpec(paths=paths, vars=VARS))
                xr.testing.assert_allclose(eager.compute(), lazy.compute())

        assert "time" in eager.indexes
        assert eager.indexes["time"].is_monotonic_increasing
        assert eager["latitude"].dims == ("y", "x")

    def test_latlon_reduced_to_grid(self, tmp_path):
        """3-D lat/lon would produce a SwathDefinition that isn't the grid."""
        obj = Wrf.read(
            ReadSpec(paths=[_raw_wrfout(tmp_path / "a.nc", "2026-07-29")], vars=VARS)
        )
        assert obj["latitude"].dims == ("y", "x")
        assert obj["longitude"].dims == ("y", "x")
        assert obj["latitude"].shape == (NY, NX)

    def test_clean_input_still_works(self, tmp_path):
        """The XTIME/3-D handling must be inert on already-clean files."""
        obj = Wrf.read(
            ReadSpec(paths=[_clean_wrf(tmp_path / "clean.nc", "2019-01-01")], vars=VARS)
        )
        assert "time" in obj.indexes
        assert obj["latitude"].dims == ("y", "x")
        assert "Temperatura" in obj.data_vars

    def test_missing_declared_var_still_raises(self, tmp_path):
        """restrict_rename_to_present filters only the class map.

        A name the *user* declared and that isn't in the file must still fail
        loudly here, rather than being silently dropped and resurfacing as a
        confusing missing-variable error at plot time.
        """
        spec = ReadSpec(
            paths=[_raw_wrfout(tmp_path / "a.nc", "2026-07-29")],
            vars={"Temperatura": {"name": "NOT_A_VAR", "unit": "kelvin"}},
        )
        with pytest.raises(ValueError):
            Wrf.read(spec)
