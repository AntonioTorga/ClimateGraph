"""Base reader for gridded NetCDF output."""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

import dask
import dask.array as da
import xarray as xr

from ClimateGraph.utils.dataset_utils import dim_reduction
from ClimateGraph.utils.general_utils import manage_path

from ..reader import Reader, ReadSpec

log = logging.getLogger(__name__)

# Module level so worker processes can import them by reference.


def _read_one(path: Path, cls: type, spec: ReadSpec) -> xr.Dataset:
    """Open one file, keep the requested slice in memory, close it."""
    with xr.open_dataset(path, engine="netcdf4", chunks=None) as ds:
        ds = cls._preprocess(ds, spec)
        # Before `load`, so a dropped level is never read off disk.
        ds = dim_reduction(ds, cls._per_file_reduce(spec), name=path.stem).load()
    # A fresh object, holding no reference to the closed file store.
    return xr.Dataset(ds.data_vars, coords=ds.coords, attrs=ds.attrs)


def _file_layout(ds: xr.Dataset, concat_dim: str) -> dict:
    """The concat coordinate and per-variable shape of one loaded file."""
    return {
        "concat": ds[concat_dim].values,
        "vars": {
            name: (ds[name].dims, ds[name].shape, ds[name].dtype)
            for name in ds.data_vars
            if name != concat_dim
        },
    }


def _static_coords(ds: xr.Dataset, names: list[str]) -> dict:
    """The coordinates every file repeats identically."""
    return {
        name: (ds[name].dims, ds[name].values) for name in names if name in ds.coords
    }


def _var_values(ds: xr.Dataset, var: str):
    return ds[var].values


class DefaultRegularGridReader(Reader):
    type_aliases = ["DefaultRegularGrid", "DefaultGrid"]
    topology = "RegularGrid"

    # Subclasses set this to map source dim/var names → canonical names.
    rename: dict[str, str] = {}

    # When True, drop rename keys absent from the piece before renaming. Left
    # False by default so a missing variable still raises (a useful error).
    # Readers whose map covers alternative source layouts (e.g. WRF, where the
    # time coordinate is `Time` in cleaned files and `XTIME` in raw output) set
    # it True, since only one of the alternatives is ever present.
    restrict_rename_to_present: bool = False

    # The dimension files are stacked along, and the coordinates that are the
    # same in every file so only the first one's are kept.
    concat_dim: str = "time"
    static_coords: tuple[str, ...] = ("latitude", "longitude")

    @classmethod
    def _resolve_paths(cls, spec: ReadSpec) -> list[Path]:
        """Glob-expand, always sorted.

        Every path this reader concatenates along ``concat_dim`` — eager,
        lazy-nested and unsafe alike — stacks in path order, so the warning
        ``manage_path`` raises on a non-sortable glob belongs here.
        """
        return manage_path(spec.paths, sort=True)

    @classmethod
    def _per_file_reduce(cls, spec: ReadSpec) -> dict:
        """The ``dim_reduce`` entries that are safe to apply to a single file.

        ``concat_dim`` is excluded: reducing it per file would collapse each
        file on its own and stack the results. ``Reader._dim_reduce`` applies
        the whole spec again afterwards, which re-applies nothing — a dim that
        was selected or reduced away is no longer in ``dims``.
        """
        reduce = spec.extras.get("dim_reduce") or {}
        return {dim: s for dim, s in reduce.items() if dim != cls.concat_dim}

    @classmethod
    def _open_many(cls, paths: list[Path], spec: ReadSpec) -> xr.Dataset:
        """Read each file eagerly in its own worker task, leaving no handle open.

        ``open_mfdataset`` opens the files one at a time — most of a 58-minute
        run over 1825 wrfout files. Opening them with ``parallel=True`` crashes
        instead: a lazy handle outlives its task and xarray's
        ``CachingFileManager`` closes it unlocked while another thread reads.
        One file per task, opened and closed in the same thread, measured
        14m02s on the same run.

        Only the concat coordinate and shapes come back to this process; the
        values stay on the workers as futures behind ``da.from_delayed``. With
        no client the lazy ``open_mfdataset`` path runs instead, so a run
        without ``workers:`` keeps its current memory profile.
        """
        try:
            from distributed import get_client

            client = get_client()
        except (ImportError, ValueError):
            return super()._open_many(paths, spec)

        # `_resolve_paths` sorts, but `_open_many` must not depend on that.
        paths = sorted(paths)
        per_file = [dataclasses.replace(spec, paths=[path]) for path in paths]
        loaded = client.map(_read_one, paths, [cls] * len(paths), per_file)
        layouts = client.gather(
            client.map(_file_layout, loaded, [cls.concat_dim] * len(paths))
        )
        statics = client.submit(
            _static_coords, loaded[0], list(cls.static_coords)
        ).result()

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
                coords={cls.concat_dim: layout["concat"]},
            )
            for future, layout in zip(loaded, layouts, strict=True)
        ]
        return xr.concat(pieces, dim=cls.concat_dim).assign_coords(statics)

    @classmethod
    def _preprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Apply the variable renaming and selection declared in the spec."""
        rename = dict(cls.rename)
        if cls.restrict_rename_to_present:
            # Only the class map is filtered — it is the one spelling out
            # alternative source layouts. Names the *user* declared stay in, so a
            # typo in a `vars:` entry still raises here rather than surfacing
            # later as a mysteriously missing variable. Dims as well as
            # variables: a grid's rename map keys on both.
            rename = {
                k: v for k, v in rename.items() if k in ds.variables or k in ds.dims
            }
        rename.update(spec.extras.get("rename", {}))
        if spec.vars is not None:
            # Skip composed vars with no file name
            rename.update(
                {d["name"]: name for name, d in spec.vars.items() if d.get("name")}
            )

        ds = ds.rename(rename)
        ds = ds.reset_coords()

        if spec.vars is not None:
            keep = set(spec.vars.keys()) | {"longitude", "latitude", "time"}
            drop = set(ds.data_vars) - keep
            ds = ds.drop_vars(drop, errors="ignore")

        ds = ds.set_coords(["latitude", "longitude"])
        return ds
