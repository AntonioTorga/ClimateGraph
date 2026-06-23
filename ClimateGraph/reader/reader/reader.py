from __future__ import annotations

import logging
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import xarray as xr

from ClimateGraph.utils.dataset_utils import _record, apply_operation, dim_reduction
from ClimateGraph.utils.general_utils import manage_path

log = logging.getLogger(__name__)

LoadMode = Literal["safe", "unsafe"]


@dataclass
class ReadSpec:
    """Bundle of everything a Reader needs to fulfil a read request.

    Carried through every lifecycle hook so subclasses can branch on any
    field without growing per-hook signatures.
    """

    paths: list[Path]
    vars: dict[str, dict[str, str]] | None = None
    load_mode: LoadMode = "safe"
    cache_dir: Path | None = None
    engine: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


class Reader(ABC):
    """Reader abstract class.

    Template-method base: ``read(spec)`` walks a fixed lifecycle and
    subclasses plug into individual hooks. No subclass should override
    ``read`` itself.

    Lifecycle (per-file hooks run in BOTH modes; the only difference is
    who drives the per-file loop)::

        read(spec):
            paths = _resolve_paths(spec)           # download/cache here
            if safe:
                ds = _open_many(paths, spec)       # internally calls
                                                   # _to_xarray + _preprocess
                                                   # per file via xarray's
                                                   # open_mfdataset(preprocess=)
            else:
                pieces = []
                for p in paths:
                    raw   = _open_one(p, spec)
                    piece = _to_xarray(raw, spec)
                    piece = _preprocess(piece, spec)
                    pieces.append(piece)
                ds = _join(pieces, spec)
            ds = _postprocess(ds, spec)
            ds = _finalize(ds, spec)            # spec-driven adjustments;
                                                # runs for every reader
    """

    registry: dict[str, dict[str, type[Reader]]] = {}
    type_aliases: list[str] = []
    topology: str

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if not hasattr(cls, "topology"):
            raise TypeError(f"{cls.__name__} must define a 'topology' attribute.")

        topology = cls.topology.lower()
        if topology not in Reader.registry:
            Reader.registry[topology] = {}

        Reader.registry[topology][cls.__name__.lower()] = cls

        # Only honour aliases declared on *this* class. Without the
        # __dict__ filter, an alias on a parent (e.g. DefaultRegularGrid)
        # would get re-bound to whichever child was imported last.
        for alias in cls.__dict__.get("type_aliases", []):
            Reader.registry[topology][alias.lower()] = cls

    # ----- registry lookup ------------------------------------------------

    @classmethod
    def get_reader_subclass(cls, topology: str, reader: str) -> type[Reader]:
        topology = topology.lower()
        reader = reader.lower()
        if topology not in cls.registry:
            raise ValueError(
                f"No topology type named {topology}. Please use one of the following: {list(cls.registry.keys())}"
            )
        try:
            return cls.registry[topology][reader]
        except KeyError as err:
            raise ValueError(f"No reader {reader} for topology {topology}") from err

    @classmethod
    def check_reader_type(cls, topology: str, reader: str) -> bool:
        return (topology.lower() in cls.registry) and (
            reader.lower() in cls.registry[topology.lower()]
        )

    # ----- public entry point --------------------------------------------

    @classmethod
    def read(cls, spec: ReadSpec) -> xr.Dataset:
        """Walk the lifecycle and return the assembled dataset."""
        local_paths = cls._resolve_paths(spec)
        if not local_paths:
            raise ValueError(
                f"{cls.__name__}._resolve_paths returned no paths for {spec.paths}"
            )

        # Replace the spec's paths with the resolved local paths so every
        # downstream hook sees the post-download view.
        spec = ReadSpec(
            paths=local_paths,
            vars=spec.vars,
            load_mode=spec.load_mode,
            cache_dir=spec.cache_dir,
            engine=spec.engine,
            extras=spec.extras,
        )

        if spec.load_mode == "safe":
            # _open_many is contracted to return a fully-preprocessed,
            # combined Dataset (the default implementation wires
            # _to_xarray + _preprocess as the open_mfdataset
            # `preprocess=` callback, per file, in parallel).
            ds = cls._open_many(local_paths, spec)
        elif spec.load_mode == "unsafe":
            pieces = []
            for path in local_paths:
                raw = cls._open_one(path, spec)
                piece = cls._to_xarray(raw, spec)
                piece = cls._preprocess(piece, spec)
                pieces.append(piece)
            ds = cls._join(pieces, spec)
        else:
            raise ValueError(
                f"Unknown load_mode {spec.load_mode!r}; expected 'safe' or 'unsafe'."
            )

        ds = cls._postprocess(ds, spec)
        ds = cls._finalize(ds, spec)
        return ds

    # ----- finalization (spec-driven, runs for every reader) --------------

    @classmethod
    def _finalize(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Apply spec-driven adjustments after ``_postprocess``.

        Grouped here rather than appended to ``read`` so the lifecycle keeps a
        single finalization seam: new config-driven transforms get sequenced
        in this method, not tacked onto ``read``. Runs for every reader,
        independent of which hooks a subclass overrode (e.g. a ``_postprocess``
        override that doesn't call ``super()``).

        Order: time-coordinate shaping before value shaping, then the
        optional save. The transforms are independent today (offset touches
        only ``time``, operations only data values), but the convention keeps
        the sequence predictable; ``_save`` is queued last so the file on disk
        reflects every adjustment.
        """
        _record(ds, f"loaded {len(spec.paths)} file(s): {[str(p) for p in spec.paths]}")
        ds = cls._apply_time_offset(ds, spec)
        ds = cls._apply_operations(ds, spec)
        ds = cls._dim_reduce(ds, spec)
        ds = cls._save(ds, spec)
        return ds

    # NetCDF filename suffixes accepted for ``save_to``.
    netcdf_suffixes: tuple[str, ...] = (".nc", ".nc4", ".netcdf", ".cdf")

    @classmethod
    def _save(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Write the finalized dataset to ``spec.extras['save_to']`` as NetCDF.

        ``save_to`` must be an exact NetCDF file path.

        Returns ``ds`` unchanged so it stays chainable in ``_finalize``.
        """
        save_to = spec.extras.get("save_to")
        if not save_to:
            return ds
        target = Path(save_to)
        if target.is_dir() or target.suffix.lower() not in cls.netcdf_suffixes:
            raise ValueError(
                f"save_to must be an exact NetCDF file path "
                f"(one of {cls.netcdf_suffixes}); got {save_to!r}."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        log.info("Writing processed dataset to %s", target)
        logging.info(f"saved to {target}")
        ds.to_netcdf(target)
        return ds

    @staticmethod
    def _dim_reduce(ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Apply per-dimension reductions from ``spec.extras['dim_reduce']``.

        No-op when the key is absent.
        """
        dr = spec.extras.get("dim_reduce")
        if not dr:
            return ds
        return dim_reduction(ds, dr, name=str(spec.paths[0].stem))

    @staticmethod
    def _apply_operations(ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Materialize each variable's optional "operation".

        Single pass, two phases. Variables without an "operation" (the base
        vars) are exposed first under their canonical name; then each variable
        with an "operation" is evaluated against those base vars
        (no operation can reference a composed var, only "pure" vars)
        """
        if not spec.vars:
            return ds

        def _key(var_name: str, var_spec: dict) -> str | None:
            """The dataset key holding this var (canonical after rename, else the
            file name), or None when it isn't in the dataset."""
            if var_name in ds:
                return var_name
            native = var_spec.get("name")
            return native if native in ds else None

        # first get base namespace — vars without an operation, by canonical name.
        base: dict[str, xr.DataArray] = dict()
        for var_name, var_spec in spec.vars.items():
            if var_spec.get("operation"):
                continue
            key = _key(var_name, var_spec)
            if key is not None:
                base[var_name] = ds[key]

        # evaluate the composed/transform vars against the base namespace.
        for var_name, var_spec in spec.vars.items():
            operation = var_spec.get("operation")
            if not operation:
                continue
            namespace = base
            self_key = _key(var_name, var_spec)
            if self_key is not None:  # in-place transform: expose own data
                namespace["x"] = ds[self_key]
                namespace[var_name] = ds[self_key]
            result = apply_operation(operation, namespace)
            # Write back to the existing key for a transform, or create the
            # composed variable under its canonical name.
            ds[self_key if self_key is not None else var_name] = result
            _record(ds, f"applied operation on {var_name!r}: {operation}")
        return ds

    # ----- lifecycle hooks (override these, not read) ---------------------

    @staticmethod
    def _apply_time_offset(ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Shift the ``time`` coordinate by ``spec.extras['time_offset']`` hours.

        Optional, off by default. Meant for datasets stored in UTC that the
        user wants on a local schedule — e.g. ``time_offset: -3`` in the data
        block reads a UTC file as UTC-3 (Chile). A no-op when the key is
        absent or zero, or when the dataset has no ``time`` coordinate.
        Fractional hours are allowed (e.g. ``5.5``).
        """
        offset = spec.extras.get("time_offset")
        if not offset or "time" not in ds.coords:
            return ds
        ds = ds.assign_coords(
            time=ds["time"] + pd.to_timedelta(float(offset), unit="h")
        )
        _record(ds, f"applied time offset {offset}h")
        return ds

    @classmethod
    def _resolve_paths(cls, spec: ReadSpec) -> list[Path]:
        """Turn the user-supplied path spec into a list of local paths.

        Default behaviour: glob-expand local paths via ``manage_path``.
        Sorted lexicographically for the unsafe path (which concats in
        input order) so an out-of-order glob doesn't silently produce a
        non-monotonic time axis. Safe path keeps native glob order
        because ``xr.open_mfdataset``'s ``combine="by_coords"`` aligns
        on coords anyway.
        """
        return manage_path(spec.paths, sort=spec.load_mode == "unsafe")

    # NetCDF defaults. Override for non-NetCDF formats; downstream
    # _to_xarray will then turn the returned raw object into a Dataset.
    # netcdf4 reads metadata via libnetcdf in C — far cheaper than
    # h5netcdf's Python-level HDF5 dimension-scale walk, which previously
    # dominated wall time on multi-file Chimere runs. Per-data-block
    # override available via ``engine:`` in the YAML data entry.
    open_engine: str = "netcdf4"

    @classmethod
    def _open_many(cls, paths: list[Path], spec: ReadSpec) -> xr.Dataset:
        """Open all files (safe path). Default implementation routes
        per-file ``_to_xarray`` + ``_preprocess`` through
        ``xr.open_mfdataset(preprocess=)`` so they run in parallel inside
        xarray's machinery and unused variables get dropped *before*
        the cross-file combine. Non-NetCDF readers override this entirely.

        ``parallel`` is disabled for ``netcdf4`` because libnetcdf is not
        thread-safe — concurrent opens raise ``NetCDF: HDF error``. Other
        engines (e.g. ``h5netcdf``) get parallel opens, so a user who
        opts into a non-default engine via the YAML ``engine:`` knob can
        try to amortise opens across threads.
        """

        def per_file(ds: xr.Dataset) -> xr.Dataset:
            ds = cls._to_xarray(ds, spec)
            ds = cls._preprocess(ds, spec)
            return ds

        engine = spec.engine or cls.open_engine
        return xr.open_mfdataset(
            paths,
            chunks="auto",
            engine=engine,
            parallel=engine != "netcdf4",
            preprocess=per_file,
        )

    @classmethod
    def _open_one(cls, path: Path, spec: ReadSpec) -> Any:
        """Open a single file (unsafe path)."""
        engine = spec.engine or cls.open_engine
        return xr.open_dataset(path, chunks="auto", engine=engine)

    @classmethod
    def _to_xarray(cls, raw: Any, spec: ReadSpec) -> xr.Dataset:
        """Coerce the raw object returned by ``_open_*`` into an
        ``xr.Dataset``. No-op for NetCDF readers. CSV/HDF5/GRIB readers
        override this.
        """
        if not isinstance(raw, xr.Dataset):
            raise TypeError(
                f"{cls.__name__}._to_xarray default expects xr.Dataset; "
                f"got {type(raw).__name__}. Override _to_xarray to convert."
            )
        return raw

    @classmethod
    def _preprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Rename/drop/index. Default: pass-through. Most subclasses override."""
        return ds

    @classmethod
    def _join(cls, pieces: list[xr.Dataset], spec: ReadSpec) -> xr.Dataset:
        """Combine per-file pieces (unsafe path only).

        Default uses ``xr.combine_nested(pieces, concat_dim="time")``,
        which trusts the input order — safe here because
        ``_resolve_paths`` sorts paths when ``load_mode == "unsafe"``.
        Readers whose files share dims but hold different variables
        (variable-per-file layouts) should override this and call
        ``xr.merge(pieces)`` instead.
        """
        if len(pieces) == 1:
            return pieces[0]
        return xr.combine_nested(pieces, concat_dim="time")

    @classmethod
    def _postprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Whole-dataset cleanup that must run regardless of load mode.
        Default: pass-through."""
        return ds
