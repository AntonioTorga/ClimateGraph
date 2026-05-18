import xarray as xr

from ..reader import Reader, ReadSpec


class DefaultPointSurfaceReader(Reader):
    type_aliases = ["DefaultPointSurface"]
    topology = "PointSurface"

    rename: dict[str, str] = {}

    @classmethod
    def _preprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        rename = dict(cls.rename)
        rename.update(spec.extras.get("rename", {}))
        if spec.vars is not None:
            rename.update({d["name"]: name for name, d in spec.vars.items()})
        if "x" in ds.coords and "site" not in ds.coords:
            rename["x"] = "site"
        return ds.rename(rename)
