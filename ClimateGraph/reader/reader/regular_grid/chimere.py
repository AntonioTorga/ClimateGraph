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

    @staticmethod
    def open_mfdataset(
        files: Path | list[Path], vars: Dict[str, Any] = None, **kwargs
    ) -> xr.Dataset:
        return super().open_mfdataset(files, vars, rename=Chimere.rename)
