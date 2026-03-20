import pytest

from pathlib import Path
import xarray as xr

from ClimateGraph.reader import Reader
from ClimateGraph.reader.reader.regular_grid.wrf import Wrf
from ClimateGraph.reader.reader.regular_grid.default import DefaultRegularGridReader


def test_wrf_is_registered():
    class_reader = Reader.get_reader_subclass("RegularGrid", "WRF")
    assert class_reader == Wrf


def test_wrf_read():
    class_reader = Reader.get_reader_subclass("RegularGrid", "WRF")
    obj = class_reader.open_mfdataset(
        [Path("test_data/wrf-2019-01.nc"), Path("test_data/wrf-2019-02.nc")],
        {"Temperatura": {"name": "T2", "unit": "kelvin"}},
    )
    print(obj)
    assert type(obj) == xr.Dataset
    assert all([x in obj.coords for x in ["latitude", "longitude"]])
    assert all(
        [x in obj.dims for x in ["time", "x", "y"]]
    )  # z will also be there if there is any var that varies over it.
    assert "Temperatura" in obj.data_vars
