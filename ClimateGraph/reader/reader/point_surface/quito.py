from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd
import xarray as xr

from ..reader import ReadSpec
from .csv_base import CSVPointSurfaceReader


class QUITO(CSVPointSurfaceReader):
    """Quito (REMMAQ) reader for the variable-per-file CSV layout.

    Layout: one CSV per pollutant, each with a ``Fecha`` column and one column
    per station (station names as headers), plus an Excel metadata sheet.
    Missing values are the literal string ``NaN``. The variable a file carries
    is NOT inferred from its name — the data block supplies an explicit
    ``var_files`` mapping ``{canonical_var: filename}``.

    Station names in the CSV headers (e.g. ``ELCAMAL``, ``GUAMANI``) are the
    ASCII-uppercased, space-stripped forms of the accented names in the Excel
    metadata (``El Camal``, ``Guamaní``); ``_norm_site_key`` reconciles them.
    """

    default_station_key = "Estación"
    default_time_col = "Fecha"
    time_format = "%d-%b-%Y %H:%M:%S"
    latlon_aliases = {"Latitud": "latitude", "Longitud": "longitude"}

    @classmethod
    def _open_one(cls, path: Path, spec: ReadSpec) -> pd.DataFrame:
        time_col = spec.extras.get("time_col", cls.default_time_col)
        df = pd.read_csv(path)
        df[time_col] = pd.to_datetime(df[time_col], format=cls.time_format)
        # Resolve which canonical variable this file holds from var_files.
        df.attrs["var"] = cls._var_for(path, spec)
        return df

    @classmethod
    def _to_xarray(cls, raw: pd.DataFrame, spec: ReadSpec) -> xr.Dataset:
        time_col = spec.extras.get("time_col", cls.default_time_col)
        canonical = raw.attrs["var"]
        # Name the single data var as the file-native name so the inherited
        # rename maps it to the canonical name (no-op when they match).
        var_name = canonical
        if spec.vars is not None and canonical in spec.vars:
            var_name = spec.vars[canonical]["name"]

        df = raw.set_index(time_col)
        df.index.name = "time"
        df.columns.name = "site"
        da = xr.DataArray(df, name=var_name)
        return da.to_dataset()

    @classmethod
    def _join(cls, pieces: list[xr.Dataset], spec: ReadSpec) -> xr.Dataset:
        # Variable-per-file: combine the differing vars on shared time/site.
        return xr.merge(pieces)

    @classmethod
    def _var_for(cls, path: Path, spec: ReadSpec) -> str:
        var_files = spec.extras.get("var_files")
        if not var_files:
            raise ValueError(
                "QUITO requires a 'var_files' mapping {canonical_var: filename} "
                "in the data block."
            )
        for canonical, filename in var_files.items():
            if Path(filename).name == path.name:
                return canonical
        raise ValueError(
            f"QUITO: file {path.name!r} not found in var_files {var_files}."
        )

    @staticmethod
    def _norm_site_key(value) -> str:
        # Strip accents, drop spaces, uppercase — turns the Excel "Guamaní" /
        # "El Camal" into the CSV headers "GUAMANI" / "ELCAMAL".
        s = unicodedata.normalize("NFKD", str(value))
        s = "".join(c for c in s if not unicodedata.combining(c))
        return s.upper().replace(" ", "")
