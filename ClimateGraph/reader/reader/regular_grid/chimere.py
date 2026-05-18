from pathlib import Path
from typing import Any

import xarray as xr

from .default import DefaultRegularGridReader


class Chimere(DefaultRegularGridReader):
    rename = {
        "nav_lat": "latitude",
        "nav_lon": "longitude",
        "time_counter": "time",
        "bottom_top": "z",
    }

    @classmethod
    def open_mfdataset(
        cls, files: Path | list[Path], vars: dict[str, Any], **kwargs
    ) -> xr.Dataset:
        rename = kwargs.get("rename", {})
        rename.update(Chimere.rename)
        xrds = super().open_mfdataset(files, vars, rename=rename)

        if "z" in list(xrds.dims):
            xrds = xrds.isel(z=0)
        return xrds
