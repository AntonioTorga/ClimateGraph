"""Shared fixtures and collection rules for the ClimateGraph test suite.

Fixtures are intentionally lightweight — they build in-memory ``xr.Dataset``
objects rather than touching disk, so most unit tests run without needing the
NetCDF samples in ``test_data/data/``. Tests that *do* need those samples
should be marked ``@pytest.mark.slow``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import cartopy.crs as ccrs
import numpy as np
import pandas as pd
import pytest
import xarray as xr


# ``test_against_manual_filter.py`` is an ad-hoc analysis script that imports
# data from a CR2 NFS share. It is not a real test; ignore it during collection
# so the rest of the suite can run.
collect_ignore = ["test_against_manual_filter.py"]


REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_DATA_DIR = REPO_ROOT / "test_data"


# ---------------------------------------------------------------------------
# In-memory dataset factories
# ---------------------------------------------------------------------------


def _make_regular_grid_dataset(
    n_time: int = 6,
    n_y: int = 4,
    n_x: int = 5,
    start: str = "2019-01-01",
    freq: str = "D",
) -> xr.Dataset:
    """Build a minimal RegularGrid-shaped xr.Dataset.

    Dims: (time, y, x). Coords: time, latitude(y,x), longitude(y,x).
    Vars: Temperatura (kelvin-ish), Presion (pascal-ish).
    """
    times = pd.date_range(start, periods=n_time, freq=freq)
    lat_1d = np.linspace(-36.0, -33.0, n_y)
    lon_1d = np.linspace(-73.0, -69.0, n_x)
    lat2d, lon2d = np.meshgrid(lat_1d, lon_1d, indexing="ij")

    rng = np.random.default_rng(seed=0)
    temp = 285.0 + rng.normal(scale=2.0, size=(n_time, n_y, n_x))
    pres = 101000.0 + rng.normal(scale=200.0, size=(n_time, n_y, n_x))

    ds = xr.Dataset(
        data_vars={
            "Temperatura": (("time", "y", "x"), temp),
            "Presion": (("time", "y", "x"), pres),
        },
        coords={
            "time": times,
            "latitude": (("y", "x"), lat2d),
            "longitude": (("y", "x"), lon2d),
        },
    )
    return ds


def _make_point_surface_dataset(
    n_time: int = 6,
    n_site: int = 3,
    start: str = "2019-01-01",
    freq: str = "D",
    regions: Iterable[int] = (13, 13, 5),
    zones: Iterable[str] = ("Litoral", "Valle", "Litoral"),
) -> xr.Dataset:
    """Build a minimal PointSurface-shaped xr.Dataset.

    Dims: (time, site). Coords: time, site, latitude(site), longitude(site),
    region(site), zonaGeografica(site). Vars: Temperatura (degC), Presion (hPa).
    """
    times = pd.date_range(start, periods=n_time, freq=freq)
    sites = np.arange(n_site)
    lat = np.linspace(-35.5, -33.5, n_site)
    lon = np.linspace(-72.0, -70.0, n_site)

    rng = np.random.default_rng(seed=1)
    temp = 12.0 + rng.normal(scale=2.0, size=(n_time, n_site))
    pres = 1010.0 + rng.normal(scale=2.0, size=(n_time, n_site))

    ds = xr.Dataset(
        data_vars={
            "Temperatura": (("time", "site"), temp),
            "Presion": (("time", "site"), pres),
        },
        coords={
            "time": times,
            "site": sites,
            "latitude": ("site", lat),
            "longitude": ("site", lon),
            "region": ("site", np.array(list(regions), dtype=int)),
            "zonaGeografica": ("site", np.array(list(zones), dtype=object)),
        },
    )
    return ds


@pytest.fixture
def regular_grid_dataset() -> xr.Dataset:
    return _make_regular_grid_dataset()


@pytest.fixture
def point_surface_dataset() -> xr.Dataset:
    return _make_point_surface_dataset()


@pytest.fixture
def make_regular_grid():
    """Factory variant for tests that need different shapes."""
    return _make_regular_grid_dataset


@pytest.fixture
def make_point_surface():
    """Factory variant for tests that need different shapes."""
    return _make_point_surface_dataset


# ---------------------------------------------------------------------------
# Stub Data subclasses — let us exercise Data ABC behaviour without IO.
# ---------------------------------------------------------------------------


@pytest.fixture
def regular_grid_data(regular_grid_dataset, monkeypatch):
    """A RegularGrid Data instance pre-loaded with the in-memory dataset.

    The reader is replaced with a no-op that returns the fixture dataset,
    so ``load_obj`` is safe to call.
    """
    from ClimateGraph.data import RegularGrid

    class _StubReader:
        @staticmethod
        def open_mfdataset(files, vars, **kwargs):
            return regular_grid_dataset

    instance = RegularGrid(
        name="grid_stub",
        path=Path("memory://grid"),
        vars={
            "Temperatura": {"name": "Temperatura", "unit": "kelvin"},
            "Presion": {"name": "Presion", "unit": "pascal"},
        },
        reader=_StubReader,
        crs=ccrs.PlateCarree(),
    )
    instance.obj = regular_grid_dataset
    return instance


@pytest.fixture
def point_surface_data(point_surface_dataset):
    """A PointSurface Data instance pre-loaded with the in-memory dataset."""
    from ClimateGraph.data import PointSurface

    class _StubReader:
        @staticmethod
        def open_mfdataset(files, vars, **kwargs):
            return point_surface_dataset

    instance = PointSurface(
        name="point_stub",
        path=Path("memory://point"),
        vars={
            "Temperatura": {"name": "Temperatura", "unit": "degC"},
            "Presion": {"name": "Presion", "unit": "hectopascal"},
        },
        reader=_StubReader,
        crs=ccrs.PlateCarree(),
    )
    instance.obj = point_surface_dataset
    return instance


# ---------------------------------------------------------------------------
# Misc fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_output_dir(tmp_path) -> Path:
    """Throwaway directory tests can write outputs into."""
    out = tmp_path / "results"
    out.mkdir()
    return out


@pytest.fixture
def test_data_dir() -> Path:
    """Repo-relative path to ``ClimateGraph/test_data``."""
    return TEST_DATA_DIR


def pytest_collection_modifyitems(config, items):
    """Auto-skip @slow tests when the sample NetCDFs are not on disk.

    Lets ``pytest`` work on fresh clones (or in CI without the data folder)
    without explicit ``-m "not slow"`` filtering.
    """
    have_samples = (TEST_DATA_DIR / "data").is_dir() and any(
        (TEST_DATA_DIR / "data").glob("*.nc")
    )
    if have_samples:
        return
    skip_slow = pytest.mark.skip(reason="NetCDF samples not present in test_data/data/")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
