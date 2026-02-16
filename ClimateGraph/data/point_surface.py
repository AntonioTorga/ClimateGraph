from .data import Data
from pathlib import Path

from pyresample.geometry import SwathDefinition


class PointSurface(Data):
    type_aliases = ["pt_sfc", "point_surface", "point"]

    def __init__(self, name: str, path: Path | list[Path], **kwargs):
        super().__init__(name, path)

    def _set_geom(self):
        lons, lats = self.get_coordinates(["longitude", "latitude"])
        swath_def = SwathDefinition(lons=lons, lats=lats, crs=self.crs)
        self.geom = swath_def.compute_optimal_bb_area(self.crs.proj4_params)
        return self.geom
