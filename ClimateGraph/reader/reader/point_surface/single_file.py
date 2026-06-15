from __future__ import annotations

from pathlib import Path

import pandas as pd
import xarray as xr

from ..reader import ReadSpec
from .csv_base import CSVPointSurfaceReader


class SingleFileReader(CSVPointSurfaceReader):
    """Reader for the single-file CSV layout (one file holds everything).

    Layout: one CSV holding every station's record, keyed by a station-code
    column, plus a ``stations.csv`` metadata table. Originally written for São
    Paulo (CETESB/QUALAR), whose defaults this keeps; its timestamps in
    ``local_date`` are tz-aware (``-03:00``) and stored as naive local
    wall-clock to stay consistent with the other in-situ readers.
    """

    type_aliases = ["single-file"]
    default_station_key = "code"
    default_time_col = "local_date"
    latlon_aliases = {"lat": "latitude", "lon": "longitude"}

    # Non-numeric columns that ride along as metadata (per ``code``) rather
    # than as data variables.
    drop_cols = ["type"]

    @classmethod
    def _open_one(cls, path: Path, spec: ReadSpec) -> pd.DataFrame:
        time_col = spec.extras.get("time_col", cls.default_time_col)
        df = pd.read_csv(path)
        # Parse the tz-aware timestamp, then drop the tz to keep naive local
        # wall-clock (xarray cannot hold tz-aware datetimes anyway).
        df[time_col] = pd.to_datetime(df[time_col]).dt.tz_localize(None)
        return df

    @classmethod
    def _to_xarray(cls, raw: pd.DataFrame, spec: ReadSpec) -> xr.Dataset:
        time_col = spec.extras.get("time_col", cls.default_time_col)
        code_col = spec.extras.get("station_key", cls.default_station_key)

        df = raw.drop(columns=cls.drop_cols, errors="ignore")
        # Collapse to one row per (time, code), taking the first non-null per
        # column so the partial rows merge rather than colliding.
        df = df.groupby([time_col, code_col]).first()
        ds = df.to_xarray()
        return ds.rename({time_col: "time", code_col: "site"})

    @classmethod
    def _join(cls, pieces: list[xr.Dataset], spec: ReadSpec) -> xr.Dataset:
        # Single file in practice; base default handles len == 1.
        return super()._join(pieces, spec)
