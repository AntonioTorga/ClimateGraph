import xarray as xr

from ..reader import Reader, ReadSpec


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

    @classmethod
    def _preprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
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
