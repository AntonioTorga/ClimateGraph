from .default import DefaultRegularGridReader

from typing import Dict, Any
from pathlib import Path
import xarray as xr


class Chimere(DefaultRegularGridReader):
    rename = {
        "nav_lat": "latitude",
        "nav_lon": "longitude",
        "time_counter": "time",
        "bottom_top": "z",
    }

    @classmethod
    def open_mfdataset(
        cls, files: Path | list[Path], vars: Dict[str, Any], **kwargs
    ) -> xr.Dataset:
        rename = kwargs.get("rename", {})
        rename.update(Chimere.rename)
        return super().open_mfdataset(files, vars, rename=rename)
