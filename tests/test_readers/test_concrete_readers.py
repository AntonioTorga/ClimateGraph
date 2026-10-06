import pytest
import xarray as xr

from ClimateGraph.reader import Reader
from ClimateGraph.reader.reader.reader import ReadSpec

pytestmark = pytest.mark.slow


@pytest.fixture
def wrf_files(test_data_dir):
    return sorted((test_data_dir / "data").glob("wrf-2019-*.nc"))


@pytest.fixture
def dmc_file(test_data_dir):
    return test_data_dir / "data" / "dmc-2010-2019.nc"


@pytest.fixture
def sinca_file(test_data_dir):
    return test_data_dir / "data" / "SINCA-CAL-Daily-2000-2026.nc"


@pytest.fixture
def chimere_file(test_data_dir):
    return test_data_dir / "data" / "chim_reduced_2021-06.nc"


def _spec(paths, vars):
    return ReadSpec(paths=list(paths), vars=vars)


class TestWrf:
    def test_open_renames_and_drops(self, wrf_files):
        reader = Reader.get_reader_subclass("RegularGrid", "wrf")
        ds = reader.read(
            _spec(wrf_files, {"Temperatura": {"name": "T2", "unit": "kelvin"}})
        )
        assert isinstance(ds, xr.Dataset)
        assert {"latitude", "longitude"}.issubset(ds.coords)
        assert {"time", "x", "y"}.issubset(ds.dims)
        assert "Temperatura" in ds.data_vars
        assert "T2" not in ds.data_vars

    def test_unused_vars_dropped(self, wrf_files):
        reader = Reader.get_reader_subclass("RegularGrid", "wrf")
        ds = reader.read(
            _spec(wrf_files, {"Temperatura": {"name": "T2", "unit": "kelvin"}})
        )
        assert "U" not in ds.data_vars
        assert "PSFC" not in ds.data_vars


class TestChimere:
    def test_open_renames_and_drops(self, chimere_file):
        reader = Reader.get_reader_subclass("RegularGrid", "chimere")
        ds = reader.read(
            _spec([chimere_file], {"PM25_var": {"name": "PM25", "unit": "ug/m**3"}})
        )
        assert isinstance(ds, xr.Dataset)
        assert {"latitude", "longitude"}.issubset(ds.coords)
        assert "time" in ds.dims
        # z (bottom_top) is preserved — level selection now happens at resample time,
        # not at read time, so the full vertical column is available downstream.
        assert "z" in ds.dims
        assert "PM25_var" in ds.data_vars

    def test_unused_vars_dropped(self, chimere_file):
        reader = Reader.get_reader_subclass("RegularGrid", "chimere")
        ds = reader.read(
            _spec([chimere_file], {"PM25_var": {"name": "PM25", "unit": "ug/m**3"}})
        )
        assert "O3" not in ds.data_vars
        assert "PM10" not in ds.data_vars


class TestDmc:
    def test_open_renames_vars(self, dmc_file):
        reader = Reader.get_reader_subclass("PointSurface", "dmc")
        ds = reader.read(
            _spec([dmc_file], {"Temperatura": {"name": "temperatura", "unit": "degC"}})
        )
        assert "Temperatura" in ds.data_vars
        assert "temperatura" not in ds.data_vars


class TestSinca:
    def test_open_renames_vars(self, sinca_file):
        reader = Reader.get_reader_subclass("PointSurface", "sinca")
        ds = reader.read(
            _spec([sinca_file], {"PM10": {"name": "PM10_ug|m3", "unit": "ug/m**3"}})
        )
        assert "PM10" in ds.data_vars
