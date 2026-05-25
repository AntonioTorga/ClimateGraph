import pytest

from ClimateGraph.reader import Reader
from ClimateGraph.reader.reader.regular_grid.default import DefaultRegularGridReader
from ClimateGraph.reader.reader.regular_grid.wrf import Wrf


class TestRegistry:
    def test_regular_grid_topology_populated(self):
        bucket = Reader.registry["regulargrid"]
        assert "wrf" in bucket
        assert "chimere" in bucket
        assert "defaultregulargridreader" in bucket

    def test_point_surface_topology_populated(self):
        bucket = Reader.registry["pointsurface"]
        assert "dmc" in bucket
        assert "sinca" in bucket
        assert "defaultpointsurfacereader" in bucket

    def test_csv_point_surface_readers_registered(self):
        bucket = Reader.registry["pointsurface"]
        # The Chile CSV reader registers under its own name plus the CHILE
        # alias, leaving the existing NetCDF SINCA reader untouched.
        assert bucket["sincacsv"].__name__ == "SINCACSV"
        assert bucket["chile"].__name__ == "SINCACSV"
        assert bucket["saopaulo"].__name__ == "SAOPAULO"
        assert bucket["quito"].__name__ == "QUITO"
        # The new readers must not shadow the existing NetCDF SINCA.
        assert bucket["sinca"].__name__ == "SINCA"

    def test_case_insensitive_lookup(self):
        assert Reader.get_reader_subclass("RegularGrid", "WRF") is Wrf
        assert Reader.get_reader_subclass("regulargrid", "wrf") is Wrf

    def test_default_alias_resolves_to_declaring_class(self):
        # type_aliases are now filtered to cls.__dict__, so the alias
        # declared on DefaultRegularGridReader resolves to it and is
        # not silently rebound to the last-imported subclass.
        resolved = Reader.get_reader_subclass("RegularGrid", "DefaultRegularGrid")
        assert resolved is DefaultRegularGridReader

    def test_unknown_topology_raises(self):
        with pytest.raises(ValueError, match="No topology"):
            Reader.get_reader_subclass("WhatIs", "wrf")

    def test_unknown_reader_for_known_topology_raises(self):
        with pytest.raises(ValueError, match="No reader"):
            Reader.get_reader_subclass("RegularGrid", "nope")

    def test_check_reader_type(self):
        assert Reader.check_reader_type("RegularGrid", "wrf") is True
        assert Reader.check_reader_type("RegularGrid", "dmc") is False
        assert Reader.check_reader_type("PointSurface", "dmc") is True

    def test_missing_topology_attr_raises(self):
        with pytest.raises(TypeError, match="topology"):

            class BadReader(Reader):
                pass
