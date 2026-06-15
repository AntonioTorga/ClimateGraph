from __future__ import annotations

from pathlib import Path

import pandas as pd
import xarray as xr

from ..reader import ReadSpec
from .csv_base import CSVPointSurfaceReader


class StationPerFileReader(CSVPointSurfaceReader):
    """Reader for the station-per-file CSV layout (one station per file).

    Layout: one CSV per station (``{station_id}.csv``) holding a time column
    plus one column per variable, accompanied by a ``stations.csv`` metadata
    table. The station id is the file's stem. Originally written for the Chile
    SINCA per-station export, whose defaults this keeps.
    """

    type_aliases = ["station-per-file"]
    default_station_key = "station_id"
    default_time_col = "timestamp"
    latlon_aliases = {"latitud": "latitude", "longitud": "longitude"}

    @classmethod
    def _open_one(cls, path: Path, spec: ReadSpec) -> pd.DataFrame:
        time_col = spec.extras.get("time_col", cls.default_time_col)
        df = pd.read_csv(path, parse_dates=[time_col])
        # Stash the station id (filename stem) for _to_xarray, which has no
        # access to the path.
        df.attrs["station_id"] = path.stem
        return df

    @classmethod
    def _to_xarray(cls, raw: pd.DataFrame, spec: ReadSpec) -> xr.Dataset:
        time_col = spec.extras.get("time_col", cls.default_time_col)
        df = raw.set_index(time_col)
        df.index.name = "time"
        ds = df.to_xarray()
        ds = ds.expand_dims(site=[raw.attrs["station_id"]])
        return ds.transpose("time", "site")

    @classmethod
    def _join(cls, pieces: list[xr.Dataset], spec: ReadSpec) -> xr.Dataset:
        if len(pieces) == 1:
            return pieces[0]
        # One station per file: stack along site (NOT the default time-concat),
        # outer-joining the time axes so stations with differing coverage align.
        return xr.concat(pieces, dim="site", join="outer")
