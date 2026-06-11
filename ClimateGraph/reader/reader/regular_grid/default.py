import xarray as xr

from ..reader import Reader, ReadSpec


class DefaultRegularGridReader(Reader):
    type_aliases = ["DefaultRegularGrid", "DefaultGrid"]
    topology = "RegularGrid"

    # Subclasses set this to map source dim/var names → canonical names.
    rename: dict[str, str] = {}

    @classmethod
    def _preprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        rename = dict(cls.rename)
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
