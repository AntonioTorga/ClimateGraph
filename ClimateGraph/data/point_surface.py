from .data import Data
from pathlib import Path

from pyresample.geometry import SwathDefinition


class PointSurface(Data):
    type_aliases = ["pt_sfc", "point_surface", "point"]

    def _set_geom(self):
        lons, lats = self.get_coordinates(["longitude", "latitude"], as_array=True)
        self._geom = SwathDefinition(lons=lons, lats=lats, crs=self.crs)
