"""Synthetic datasets for the documentation examples.

Run ``generate_figures.py`` to rebuild the figures in the documentation.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

LON_MIN, LON_MAX = -71.2, -70.4
LAT_MIN, LAT_MAX = -33.7, -33.2

STATIONS = [
    ("Independencia", -70.664, -33.422),
    ("La Florida", -70.588, -33.517),
    ("Las Condes", -70.523, -33.377),
    ("Pudahuel", -70.750, -33.437),
    ("Puente Alto", -70.592, -33.591),
    ("Quilicura", -70.740, -33.367),
]


def _diurnal(hours: np.ndarray) -> np.ndarray:
    """Two-peaked daily cycle: morning rush and a stronger evening inversion."""
    morning = np.exp(-0.5 * ((hours - 8) / 2.0) ** 2)
    evening = np.exp(-0.5 * ((hours - 21) / 3.0) ** 2)
    return 0.7 * morning + 1.0 * evening


def _weekly(dayofweek: np.ndarray) -> np.ndarray:
    """Weekends are cleaner."""
    return np.where(dayofweek >= 5, 0.72, 1.0)


def make_grid(path: Path, nx: int = 30, ny: int = 22, days: int = 14) -> Path:
    """Write a gridded NetCDF shaped like regional model output.

    Dimensions are ``(time, y, x)`` with two-dimensional ``longitude`` and
    ``latitude`` coordinates, which is what
    :class:`~ClimateGraph.data.RegularGrid` expects.
    """
    time = pd.date_range("2021-06-01", periods=days * 24, freq="h")
    lon1d = np.linspace(LON_MIN, LON_MAX, nx)
    lat1d = np.linspace(LAT_MIN, LAT_MAX, ny)
    lon2d, lat2d = np.meshgrid(lon1d, lat1d)

    hours = time.hour.to_numpy().astype(float)
    dow = time.dayofweek.to_numpy()
    temporal = _diurnal(hours) * _weekly(dow)

    # Pollution accumulates in the low west of the basin and thins to the east,
    # where the ground rises toward the Andes.
    west_east = (LON_MAX - lon2d) / (LON_MAX - LON_MIN)
    basin = 0.45 + 1.15 * west_east**1.4

    rng = np.random.default_rng(20210601)
    base = 28.0
    field = (
        base
        * basin[None, :, :]
        * (0.55 + 1.25 * temporal[:, None, None])
        * (1.0 + 0.12 * rng.standard_normal((time.size, ny, nx)))
    )
    field = np.clip(field, 1.0, None)


    ds = xr.Dataset(
        {
            "pm25": (("time", "y", "x"), field.astype("float32")),
        },
        coords={
            "time": time,
            "longitude": (("y", "x"), lon2d),
            "latitude": (("y", "x"), lat2d),
        },
    )
    ds["pm25"].attrs["units"] = "ug/m3"
    ds.attrs["title"] = "Synthetic gridded model output for the ClimateGraph docs"

    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = {v: {"zlib": True, "complevel": 5} for v in ds.data_vars}
    ds.to_netcdf(path, encoding=encoding)
    return path


def make_stations(path: Path, days: int = 14) -> Path:
    """Write a station NetCDF shaped like a monitoring network.

    Dimensions are ``(time, site)`` with one-dimensional coordinates, which is
    what :class:`~ClimateGraph.data.PointSurface` expects.
    """
    time = pd.date_range("2021-06-01", periods=days * 24, freq="h")
    names = [s[0] for s in STATIONS]
    lons = np.array([s[1] for s in STATIONS])
    lats = np.array([s[2] for s in STATIONS])

    hours = time.hour.to_numpy().astype(float)
    dow = time.dayofweek.to_numpy()
    temporal = _diurnal(hours) * _weekly(dow)

    west_east = (LON_MAX - lons) / (LON_MAX - LON_MIN)
    basin = 0.45 + 1.15 * west_east**1.4

    rng = np.random.default_rng(1987)
    base = 28.0
    values = (
        base
        * basin[None, :]
        * (0.55 + 1.25 * temporal[:, None])
        * (1.0 + 0.22 * rng.standard_normal((time.size, len(STATIONS))))
    )
    # Observations are noisier than the model and biased a little high, which is
    # what makes the comparison plots worth looking at.
    values = np.clip(values * 1.12, 0.5, None)

    # Real networks have gaps.
    gaps = rng.random(values.shape) < 0.04
    values[gaps] = np.nan

    ds = xr.Dataset(
        {"pm25": (("time", "site"), values.astype("float32"))},
        coords={
            "time": time,
            "site": names,
            "longitude": ("site", lons),
            "latitude": ("site", lats),
        },
    )
    ds["pm25"].attrs["units"] = "ug/m3"
    ds.attrs["title"] = "Synthetic station observations for the ClimateGraph docs"

    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = {v: {"zlib": True, "complevel": 5} for v in ds.data_vars}
    ds.to_netcdf(path, encoding=encoding)
    return path
