from ..reader import Reader
from pathlib import Path
import xarray as xr


class DefaultRegularGridReader(Reader):
    type_aliases = ["DefaultRegularGrid", "DefaultGrid"]

    @staticmethod
    def open_mfdataset(
        files: list[Path] | Path, var_list: dict, **kwargs
    ) -> xr.Dataset:

        xrds = xr.open_mfdataset(
            files,
            chunks="auto",
            combine="by_coords",
        )

        if (rename_dict := kwargs.get("rename")) is not None:
            xrds = xrds.rename(rename_dict)

        drop_data_vars = (
            set(list(xrds.data_vars)) - set(var_list) if var_list != None else set()
        )

        xrds = xrds.drop_vars(drop_data_vars, errors="ignore")

        xrds = xrds.reset_coords()
        xrds = xrds.set_coords(["latitude", "longitude"])

        return xrds
