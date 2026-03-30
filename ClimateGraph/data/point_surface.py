from .data import Data
from pathlib import Path

from pyresample.geometry import SwathDefinition


class PointSurface(Data):
    """The PointSurface topology class.

    A class that gives particular representation to Point Surface data. This data should be in ("time", "site") dimensions.
    """

    type_aliases = ["pt_sfc", "point_surface", "point"]

    def _set_geom(self):
        """_set_geom Method for setting the Pyresample Geometry object used for resampling. In this case it is a SwathDefinition object."""
        lons, lats = self.get_coordinates(["longitude", "latitude"], as_array=True)
        self._geom = SwathDefinition(lons=lons, lats=lats, crs=self.crs)
