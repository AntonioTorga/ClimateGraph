"""Tests for the CHIMERE reader and the per-file reduction it depends on.

CHIMERE writes species in 3-D. The eager read holds every file's result in
worker memory, so a decade of 20 levels would not fit: the ``z`` selection has
to happen per file, before the values are read off disk.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from ClimateGraph.reader.reader.reader import ReadSpec
from ClimateGraph.reader.reader.regular_grid.chimere import Chimere

NY, NX, NZ = 3, 4, 5
VARS = {"Ozono": {"name": "O3", "unit": "ug/m**3"}}


def _chimere_like(path: Path, start: str, hours: int = 24) -> Path:
    """A file shaped like CHIMERE output: NEMO-style coords, species in 3-D."""
    times = pd.date_range(start, periods=hours, freq="h")
    lat2d, lon2d = np.meshgrid(np.arange(NY), np.arange(NX), indexing="ij")
    ds = xr.Dataset(
        {
            "O3": (
                ("time_counter", "bottom_top", "south_north", "west_east"),
                np.arange(hours * NZ * NY * NX, dtype="float32").reshape(
                    hours, NZ, NY, NX
                ),
            )
        },
        coords={
            "time_counter": times,
            "nav_lat": (("south_north", "west_east"), lat2d.astype(float)),
            "nav_lon": (("south_north", "west_east"), lon2d.astype(float)),
        },
    )
    ds.to_netcdf(path)
    return path


def test_chimere_renames_into_the_common_layout(tmp_path):
    """`nav_lat`/`nav_lon`/`time_counter` must land on the canonical names."""
    obj = Chimere.read(
        ReadSpec(paths=[_chimere_like(tmp_path / "a.nc", "2019-01-01")], vars=VARS)
    )
    assert "time" in obj.indexes
    assert obj["latitude"].dims == ("south_north", "west_east")
    assert "Ozono" in obj.data_vars


def test_per_file_reduce_drops_the_concat_dim():
    """Reducing the concat dim per file would collapse each file on its own.

    `dim_reduce: {time: mean}` over 3650 files has to mean one value, not 3650
    daily means stacked back up.
    """
    spec = ReadSpec(
        paths=[Path("a.nc")],
        vars=VARS,
        extras={"dim_reduce": {"z": {"method": "isel", "value": 0}, "time": "mean"}},
    )
    assert Chimere._per_file_reduce(spec) == {"z": {"method": "isel", "value": 0}}


@pytest.mark.parametrize("level", [0, 2])
def test_z_selection_applies_per_file(tmp_path, level):
    """The declared level must be the one that survives, not just any level."""
    spec = ReadSpec(
        paths=[_chimere_like(tmp_path / "a.nc", "2019-01-01")],
        vars=VARS,
        extras={"dim_reduce": {"z": {"method": "isel", "value": level}}},
    )
    obj = Chimere.read(spec)
    assert "z" not in obj.dims

    expected = xr.open_dataset(tmp_path / "a.nc")["O3"].isel(bottom_top=level)
    np.testing.assert_allclose(obj["Ozono"].values, expected.values)


@pytest.mark.slow
def test_eager_read_selects_the_level_before_loading(tmp_path):
    """Under a client the level must be gone by the time values leave the task.

    This is the whole point for CHIMERE: 20 levels resident across a decade is
    what makes the eager read impossible, so the selection cannot wait for
    `Reader._dim_reduce`.
    """
    pytest.importorskip("distributed")
    from distributed import Client, LocalCluster

    paths = [
        _chimere_like(tmp_path / "a.nc", "2019-01-01"),
        _chimere_like(tmp_path / "b.nc", "2019-01-02"),
    ]
    extras = {"dim_reduce": {"z": {"method": "isel", "value": 0}}}
    lazy = Chimere.read(ReadSpec(paths=paths, vars=VARS, extras=extras))

    with LocalCluster(n_workers=2, threads_per_worker=1, processes=True) as cluster:
        with Client(cluster):
            eager = Chimere.read(ReadSpec(paths=paths, vars=VARS, extras=extras))
            # The shape the worker shipped, before `Reader._dim_reduce` could act.
            assert "z" not in eager["Ozono"].dims
            xr.testing.assert_allclose(eager.compute(), lazy.compute())

    assert eager.sizes["time"] == 48
    assert eager.indexes["time"].is_monotonic_increasing
