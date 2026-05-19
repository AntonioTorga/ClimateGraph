from __future__ import annotations

import logging
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import xarray as xr

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
        return ds

    # ----- lifecycle hooks (override these, not read) ---------------------

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
    open_engine: str = "h5netcdf"

    @classmethod
    def _open_many(cls, paths: list[Path], spec: ReadSpec) -> xr.Dataset:
        """Open all files (safe path). Default implementation routes
        per-file ``_to_xarray`` + ``_preprocess`` through
        ``xr.open_mfdataset(preprocess=)`` so they run in parallel inside
        xarray's machinery and unused variables get dropped *before*
        the cross-file combine. Non-NetCDF readers override this entirely.
        """

        def per_file(ds: xr.Dataset) -> xr.Dataset:
            ds = cls._to_xarray(ds, spec)
            ds = cls._preprocess(ds, spec)
            return ds

        return xr.open_mfdataset(
            paths,
            chunks="auto",
            engine=cls.open_engine,
            parallel=True,
            preprocess=per_file,
        )

    @classmethod
    def _open_one(cls, path: Path, spec: ReadSpec) -> Any:
        """Open a single file (unsafe path)."""
        return xr.open_dataset(path, chunks="auto", engine=cls.open_engine)

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
