import pkgutil
import importlib

for module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{module.name}")

from .data import Data
from .point_surface import PointSurface
from .regular_grid import RegularGrid
from .satellite_swath import SatelliteSwath

__all__ = ["Data", "PointSurface", "RegularGrid", "SatelliteSwath"]
