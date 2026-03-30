from pathlib import Path
import xarray as xr

from ..reader import Reader


class DMC(Reader):
    topology = "PointSurface"

    @classmethod
    def open_mfdataset(
        cls, files: list[Path] | Path, vars: dict, **kwargs
    ) -> xr.Dataset:
        obj = xr.open_mfdataset(files, chunks="auto")

        rename = {}
        if rename_dict := kwargs.get("rename", False):
            rename.update(rename_dict)
        rename.update({_dict["name"]: name for name, _dict in vars.items()})
        if ("x" in obj.coords) and ("site" not in obj.coords):
            rename.update({"x": "site"})

        obj = obj.rename(rename)

        return obj
