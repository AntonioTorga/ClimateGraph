from pathlib import Path

import pytest
import xarray as xr

from ClimateGraph.reader import Reader
from ClimateGraph.reader.reader.reader import ReadSpec
from ClimateGraph.reader.reader.regular_grid.wrf import Wrf


def test_wrf_is_registered():
    class_reader = Reader.get_reader_subclass("RegularGrid", "WRF")
    assert class_reader == Wrf


@pytest.mark.slow
def test_wrf_read():
    class_reader = Reader.get_reader_subclass("RegularGrid", "WRF")
    spec = ReadSpec(
        paths=[
            Path("test_data/data/wrf-2019-01.nc"),
            Path("test_data/data/wrf-2019-02.nc"),
        ],
        vars={"Temperatura": {"name": "T2", "unit": "kelvin"}},
    )
    obj = class_reader.read(spec)
    assert isinstance(obj, xr.Dataset)
    assert all(x in obj.coords for x in ["latitude", "longitude"])
    assert all(x in obj.dims for x in ["time", "x", "y"])
    assert "Temperatura" in obj.data_vars
