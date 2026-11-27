"""Reader for WRF model output."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import dask
import dask.array as da
import xarray as xr

from ..reader import ReadSpec
from .default import DefaultRegularGridReader

# Module level so worker processes can import them by reference.


def _read_one(path: Path, cls: type, spec: ReadSpec) -> xr.Dataset:
    """Open one file, keep the requested variables in memory, close it."""
    with xr.open_dataset(path, engine="netcdf4", chunks=None) as ds:
        ds = cls._preprocess(ds, spec).load()
    # A fresh object, holding no reference to the closed file store.
    return xr.Dataset(ds.data_vars, coords=ds.coords, attrs=ds.attrs)


def _file_layout(ds: xr.Dataset) -> dict:
    """The timestamps and per-variable shape of one loaded file."""
    return {
        "time": ds["time"].values,
        "vars": {
            name: (ds[name].dims, ds[name].shape, ds[name].dtype)
            for name in ds.data_vars
            if name != "time"
        },
    }


def _grid_coords(ds: xr.Dataset) -> dict:
    """The static 2-D lat/lon, which every file repeats."""
    return {c: (ds[c].dims, ds[c].values) for c in ("latitude", "longitude")}


def _var_values(ds: xr.Dataset, var: str):
    return ds[var].values


class Wrf(DefaultRegularGridReader):
    # `Time` and `XTIME` are alternatives, never both: cleaned NetCDF carries an
    # indexed `Time` coordinate, while raw wrfout leaves `Time` a bare dimension
    # and puts the valid times in `XTIME`. restrict_rename_to_present keeps
    # whichever the file actually has.
    rename = {
        "Time": "time",
        "XTIME": "time",
        "south_north": "y",
        "west_east": "x",
        "bottom_top": "z",
        "XLONG": "longitude",
        "XLAT": "latitude",
    }
    restrict_rename_to_present = True
    # Raw wrfout has no time index until `_postprocess` builds one, so the
    # combine orders files by path instead of by coordinate.
    combine_kwargs = {"combine": "nested", "concat_dim": "time"}

    @classmethod
    def _open_many(cls, paths: list[Path], spec: ReadSpec) -> xr.Dataset:
        """Read each file eagerly in its own worker task, leaving no handle open.

        ``open_mfdataset`` opens the files one at a time — most of a 58-minute
        run over 1825 of them. Opening them with ``parallel=True`` crashes
        instead: a lazy handle outlives its task and xarray's
        ``CachingFileManager`` closes it unlocked while another thread reads.
        One file per task, opened and closed in the same thread, measured
        14m22s on the same run.

        Only timestamps and shapes come back to this process; the values stay
        on the workers as futures behind ``da.from_delayed``. With no client
        the lazy ``open_mfdataset`` path runs instead, so a run without
        ``workers:`` keeps its current memory profile.
        """
        try:
            from distributed import get_client

            client = get_client()
        except (ImportError, ValueError):
            return super()._open_many(paths, spec)

        paths = sorted(paths)
        per_file = [dataclasses.replace(spec, paths=[path]) for path in paths]
        loaded = client.map(_read_one, paths, [cls] * len(paths), per_file)
        layouts = client.gather(client.map(_file_layout, loaded))
        grid = client.submit(_grid_coords, loaded[0]).result()

        pieces = [
            xr.Dataset(
                {
                    name: (
                        dims,
                        da.from_delayed(
                            dask.delayed(_var_values)(future, name), shape, dtype
                        ),
                    )
                    for name, (dims, shape, dtype) in layout["vars"].items()
                },
                coords={"time": layout["time"]},
            )
            for future, layout in zip(loaded, layouts, strict=True)
        ]
        return xr.concat(pieces, dim="time").assign_coords(grid)

    @classmethod
    def _preprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Rename/drop, plus the lat/lon shape raw wrfout differs in.

        WRF writes ``XLAT``/``XLONG`` once per output time even though the grid
        is static, leaving them 3-D — which breaks the ``SwathDefinition`` that
        ``RegularGrid._set_geom`` builds for resampling.

        A no-op on input that already has 2-D lat/lon. Reads no values, so the
        lazy path does not touch all 1825 files while opening them.
        """
        ds = super()._preprocess(ds, spec)

        for coord in ("latitude", "longitude"):
            if coord in ds.coords and "time" in ds[coord].dims:
                ds = ds.assign_coords({coord: ds[coord].isel(time=0, drop=True)})

        return ds

    @classmethod
    def _postprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Promote ``time`` to an index, once, after the files are combined.

        Renaming ``XTIME`` does not carry an index across, and ``reset_coords()``
        in the parent demotes a non-index ``time`` to a data variable. A no-op
        for ``_open_many``, which gets its index from the gathered timestamps;
        it serves the lazy and unsafe paths, which concat in path order.
        """
        ds = super()._postprocess(ds, spec)

        if "time" in ds.variables and "time" not in ds.indexes:
            ds = ds.set_index(time="time")

        return ds
