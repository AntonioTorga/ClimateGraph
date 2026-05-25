import xarray as xr

from ..reader import Reader, ReadSpec


class DefaultPointSurfaceReader(Reader):
    type_aliases = ["DefaultPointSurface"]
    topology = "PointSurface"

    rename: dict[str, str] = {}

    # When True, drop rename keys that aren't present in the piece before
    # renaming. NetCDF readers leave this False so a missing variable still
    # raises (a useful error). Variable-per-file readers (CSV/Excel) set it
    # True: each piece holds only one variable, so the full rename map would
    # otherwise reference names absent from that piece and ``rename`` would
    # raise.
    restrict_rename_to_present: bool = False

    @classmethod
    def _preprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        rename = dict(cls.rename)
        rename.update(spec.extras.get("rename", {}))
        if spec.vars is not None:
            rename.update({d["name"]: name for name, d in spec.vars.items()})
        if "x" in ds.coords and "site" not in ds.coords:
            rename["x"] = "site"
        if cls.restrict_rename_to_present:
            rename = {k: v for k, v in rename.items() if k in ds.variables}
        return ds.rename(rename)
