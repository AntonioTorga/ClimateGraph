from .data import Data
from ..reader import Reader
from pathlib import Path
from pyresample import SwathDefinition
import cartopy.crs as ccrs

ccrs.AzimuthalEquidistant


class RegularGrid(Data):
    type_aliases = ["regular_grid", "grid", "regulargrid"]

    def _set_geom(self):
        lons, lats = self.get_coordinates(["longitude", "latitude"], as_array=True)
        self._geom = SwathDefinition(lons=lons, lats=lats, crs=self.crs)
