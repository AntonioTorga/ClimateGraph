from collections.abc import Sequence
from pathlib import Path

import cartopy.crs as ccrs
import numpy as np
import xarray as xr
from pyresample.geometry import SwathDefinition

from .data import Data


class _PrebuiltReader:
    """No-op reader for in-memory PointSurface objects whose ``obj`` is set directly.

    ``from_points`` builds the dataset itself, so ``read`` is never reached; it
    only exists to satisfy ``Data.__init__``/``copy`` which carry a reader around.
    """

    @staticmethod
    def read(spec):
        raise RuntimeError(
            "_PrebuiltReader has no files to read; its obj is set in-memory."
        )


class PointSurface(Data):
    """The PointSurface topology class.

    A class that gives particular representation to Point Surface data. This data should be in ("time", "site") dimensions.
    """

    aliases = ["pt_sfc", "point_surface", "point"]
    geom_dims = ("site",)

    def _set_geom(self):
        """_set_geom Method for setting the Pyresample Geometry object used for resampling. In this case it is a SwathDefinition object."""
        lons, lats = self.get_coordinates(["longitude", "latitude"], as_array=True)
        self._geom = SwathDefinition(lons=lons, lats=lats, crs=self.crs)

    @classmethod
    def from_points(
        cls,
        name: str,
        names: Sequence[str],
        lats: Sequence[float],
        lons: Sequence[float],
        crs: ccrs.CRS | None = None,
    ) -> "PointSurface":
        """Build an in-memory point target from named coordinates.

        Used as the resample target of a ``Points`` domain: a coords-only
        PointSurface whose ``site`` dimension holds the provided **names**, with
        ``latitude``/``longitude`` on ``site`` (so ``_set_geom`` can build the
        SwathDefinition). No data variables — the resample only needs the geometry
        and the site-scoped coords. ``obj`` is set directly, so no reader runs.

        Parameters
        ----------
        name : str
            Identity for the target (used in the resample cache key / history).
        names : Sequence[str]
            Point names — become the ``site`` index (labels and ``.sel`` keys).
        lats, lons : Sequence[float]
            Latitude / longitude per point, in the ``crs`` (default lat/lon).
        crs : ccrs.CRS | None, optional
            Coordinate reference system. Defaults to ``PlateCarree`` (lat/lon).

        Returns
        -------
        PointSurface
            An in-memory point target ready to resample onto.
        """
        site = np.asarray(list(names), dtype=object)
        ds = xr.Dataset(
            coords={
                "site": site,
                "latitude": ("site", np.asarray(lats, dtype=float)),
                "longitude": ("site", np.asarray(lons, dtype=float)),
            }
        )
        instance = cls(
            name=name,
            path=Path(f"memory://{name}"),
            vars=None,
            reader=_PrebuiltReader,
            crs=crs or ccrs.PlateCarree(),
        )
        instance.obj = ds
        return instance
