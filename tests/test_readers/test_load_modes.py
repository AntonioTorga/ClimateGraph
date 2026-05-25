"""Safe vs unsafe load-mode equivalence on real NetCDF samples.

Roadmap issue J asks for this regression net: a small file read both ways
should produce equal data. Diverging assertions here would mean the unsafe
path's per-file preprocess + concat is drifting from the safe path's fused
``open_mfdataset`` walk.
"""

import pytest
import xarray as xr

from ClimateGraph.reader import Reader
from ClimateGraph.reader.reader.reader import ReadSpec

pytestmark = pytest.mark.slow


@pytest.fixture
def wrf_files(test_data_dir):
    return sorted((test_data_dir / "data").glob("wrf-2019-*.nc"))


@pytest.fixture
def sinca_file(test_data_dir):
    return test_data_dir / "data" / "SINCA-CAL-Daily-2000-2026.nc"


def _read(topology, name, paths, vars, mode):
    cls = Reader.get_reader_subclass(topology, name)
    return cls.read(ReadSpec(paths=list(paths), vars=vars, load_mode=mode))


def test_wrf_safe_unsafe_equivalent(wrf_files):
    vars_ = {"Temperatura": {"name": "T2", "unit": "kelvin"}}
    safe = _read("RegularGrid", "wrf", wrf_files, vars_, "safe")
    unsafe = _read("RegularGrid", "wrf", wrf_files, vars_, "unsafe")
    xr.testing.assert_equal(safe[["Temperatura"]], unsafe[["Temperatura"]])


def test_sinca_safe_unsafe_equivalent(sinca_file):
    vars_ = {"PM10": {"name": "PM10_ug|m3", "unit": "ug/m**3"}}
    safe = _read("PointSurface", "sinca", [sinca_file], vars_, "safe")
    unsafe = _read("PointSurface", "sinca", [sinca_file], vars_, "unsafe")
    xr.testing.assert_equal(safe[["PM10"]], unsafe[["PM10"]])
