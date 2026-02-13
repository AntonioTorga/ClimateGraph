from .data import Data
from ..reader import Reader
from pathlib import Path
from pyresample import AreaDefinition
import cartopy.crs as ccrs


class RegularGrid(Data):
    def __init__(self,
                name: str,
                path: Path | list[Path],
                vars: str | list[str] | None = None,
                crs: ccrs.CRS | None = None,
                **kwargs):
        super().__init__(name, path)

    def _set_geom(self):
        self.geom = AreaDefinition(
            area_id=f"area_{self.name}",
            description=f"Regular grid area definition for {self.name} dataset.",
            projection=self.crs,
            area_extent=self.bbox,
            width=self.dims["x"],
            height=self.dims["y"],
        )
