from Data.PointSurface import PointSurface
from Data.RegularGrid import RegularGrid
from Data.SatelliteSwath import SatelliteSwath
from Data.Data import Data


def contourf(data: RegularGrid | SatelliteSwath):
    print(f"Creating countourf based on {data.name}.")


def timeseries(data: Data):
    print(f"Creating timeseries based on {data.name}")
