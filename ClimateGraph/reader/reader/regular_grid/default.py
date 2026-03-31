from ..reader import Reader
from pathlib import Path
import xarray as xr


class DefaultRegularGridReader(Reader):
    type_aliases = ["DefaultRegularGrid", "DefaultGrid"]
    topology = "RegularGrid"

    @classmethod
    def open_mfdataset(
        cls, files: list[Path] | Path, vars: dict, **kwargs
    ) -> xr.Dataset:

        xrds = xr.open_mfdataset(files, chunks="auto", engine="h5netcdf")

        rename_dict = kwargs.get("rename", {})
        if vars is not None:
            rename_dict.update({_dict["name"]: name for name, _dict in vars.items()})

        xrds = xrds.rename(rename_dict)

        drop_data_vars = (
            set(list(xrds.data_vars)) - set(vars.keys()) if vars != None else set()
        )

        xrds = xrds.drop_vars(drop_data_vars, errors="ignore")

        xrds = xrds.reset_coords()
        xrds = xrds.set_coords(["latitude", "longitude"])

        return xrds
