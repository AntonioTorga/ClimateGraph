from __future__ import annotations

from pathlib import Path

import pandas as pd
import xarray as xr

from ..reader import ReadSpec
from .default import DefaultPointSurfaceReader


class CSVPointSurfaceReader(DefaultPointSurfaceReader):
    """Shared base for CSV/Excel point-surface readers.

    The layout-specific readers (station-per-file, single-file,
    variable-per-file) live in CSV/Excel rather than NetCDF and share three
    concerns this base centralises:

    1. **Per-file open is not NetCDF.** The default ``_open_many`` uses
       ``xr.open_mfdataset``; here it routes safe-mode through the exact same
       per-file loop the unsafe path runs, so the two modes are identical for
       CSV input (subclasses only implement ``_open_one`` / ``_to_xarray``).
    2. **A station-metadata join.** ``_postprocess`` attaches every column of a
       sidecar metadata table onto the ``site`` dimension as a coordinate,
       including the ``latitude``/``longitude`` that ``PointSurface._set_geom``
       requires.
    3. **The canonical-name rename** is reused from ``DefaultPointSurfaceReader``
       (variable-per-file layouts set ``restrict_rename_to_present``).

    Subclasses set ``default_station_key``, ``default_time_col`` and
    ``latlon_aliases`` and implement ``_open_one`` / ``_to_xarray`` / ``_join``.
    """

    # Pieces hold one (variable-per-file) or a disjoint set (station-per-file)
    # of vars; filter the rename map to what's actually present in each piece.
    restrict_rename_to_present = True

    # Subclass-supplied defaults; overridable per data block via ``spec.extras``.
    default_station_key: str = "station_id"
    default_time_col: str = "time"
    # Maps the metadata file's lat/lon column names onto the canonical
    # ``latitude``/``longitude`` the rest of the pipeline expects.
    latlon_aliases: dict[str, str] = {}

    # ----- safe == unsafe for CSV ----------------------------------------

    @classmethod
    def _open_many(cls, paths: list[Path], spec: ReadSpec) -> xr.Dataset:
        """Run the per-file hooks in a plain loop (mirrors the unsafe path).

        ``xr.open_mfdataset`` only understands NetCDF-like engines, so the
        default safe-mode implementation can't be used. Routing both modes
        through the same loop also makes ``safe`` and ``unsafe`` produce
        byte-identical datasets for CSV input.
        """
        pieces = [
            cls._preprocess(cls._to_xarray(cls._open_one(p, spec), spec), spec)
            for p in paths
        ]
        return cls._join(pieces, spec)

    # ----- metadata join --------------------------------------------------

    @classmethod
    def _postprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        ds = cls._attach_metadata(ds, spec)
        return super()._postprocess(ds, spec)

    @classmethod
    def _attach_metadata(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Join a station-metadata table onto the ``site`` dimension.

        Every metadata column becomes a ``(site,)`` coordinate. Stations with
        no matching metadata row get NaN-filled coordinates rather than being
        dropped. The join keys are normalised on both sides via
        ``_norm_site_key`` so e.g. integer ids in the metadata match string
        filename-stem ids on the data, or accented station names match their
        ASCII-uppercased CSV column headers (see subclass overrides).
        """
        meta_path = spec.extras.get("metadata")
        if meta_path is None:
            raise ValueError(
                f"{cls.__name__} requires a 'metadata' path in the data block."
            )
        meta = cls._read_metadata(Path(meta_path))

        key = spec.extras.get("station_key", cls.default_station_key)
        if key not in meta.columns:
            raise ValueError(
                f"{cls.__name__}: station key {key!r} not in metadata columns "
                f"{list(meta.columns)}."
            )
        meta = meta.set_index(key).rename(columns=cls.latlon_aliases)

        # Normalise the metadata index to the canonical join key and drop any
        # duplicate stations (keep first) so reindex can align unambiguously.
        meta.index = [cls._norm_site_key(v) for v in meta.index]
        meta = meta[~meta.index.duplicated(keep="first")]

        site_keys = [cls._norm_site_key(v) for v in ds["site"].values]
        meta = meta.reindex(site_keys)

        for col in meta.columns:
            ds = ds.assign_coords({col: ("site", meta[col].to_numpy())})
        return ds

    @staticmethod
    def _read_metadata(path: Path) -> pd.DataFrame:
        """Read the metadata sidecar — Excel by suffix, else CSV."""
        if path.suffix.lower() in (".xlsx", ".xls"):
            return pd.read_excel(path, engine="openpyxl")
        return pd.read_csv(path)

    @staticmethod
    def _norm_site_key(value) -> str:
        """Canonicalise a station id for the metadata join.

        Numeric ids (whether stored as ``int``, ``float`` like ``109.0``, or
        the string ``"104"``) collapse to their integer string form so that a
        filename stem matches an ``int`` metadata id. Everything else is
        stringified and stripped. Subclasses with text station names (e.g.
        variable-per-file with accented headers) override this.
        """
        try:
            f = float(value)
        except (ValueError, TypeError):
            return str(value).strip()
        return str(int(f)) if f == int(f) else str(f)
