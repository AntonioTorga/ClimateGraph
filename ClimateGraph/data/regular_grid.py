from .data import Data
from ..reader import Reader
from pathlib import Path
from pyresample import SwathDefinition
import cartopy.crs as ccrs

ccrs.AzimuthalEquidistant


class RegularGrid(Data):
    """The RegularGrid topology class.

    A class that implements Regular Grid specific logic. This data should be in ("time", "x", "y", "z") dimensions.
    """

    type_aliases = ["regular_grid", "grid", "regulargrid"]

    def _set_geom(self):
        """_set_geom Method for setting the Pyresample Geometry object used for resampling. In this case it is a SwathDefinition object because the AreaDefinition isn't working correctly"""
        # TODO: change to AreaDefinition
        lons, lats = self.get_coordinates(["longitude", "latitude"], as_array=True)
        self._geom = SwathDefinition(lons=lons, lats=lats, crs=self.crs)
