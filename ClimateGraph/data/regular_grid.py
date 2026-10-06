"""Structured latitude/longitude grid topology."""

from pyresample import SwathDefinition

from .data import Data


class RegularGrid(Data):
    """The RegularGrid topology class.

    A class that implements Regular Grid specific logic. This data should be in ("time", "x", "y", "z") dimensions.
    """

    aliases = ["regular_grid", "grid", "regulargrid"]
    geom_dims = ("x", "y")

    def _set_geom(self):
        """Build the pyresample geometry.

        Uses a ``SwathDefinition`` rather than an ``AreaDefinition``, which does
        not behave correctly here.
        """
        # TODO: change to AreaDefinition
        lons, lats = self.get_coordinates(["longitude", "latitude"], as_array=True)
        self._geom = SwathDefinition(lons=lons, lats=lats, crs=self.crs)
