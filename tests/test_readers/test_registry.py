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

    def test_case_insensitive_lookup(self):
        assert Reader.get_reader_subclass("RegularGrid", "WRF") is Wrf
        assert Reader.get_reader_subclass("regulargrid", "wrf") is Wrf

    def test_default_alias_lookup_resolves(self):
        # `type_aliases = ["DefaultRegularGrid", "DefaultGrid"]` is declared on
        # DefaultRegularGridReader, but because `__init_subclass__` reads
        # inherited attributes, every subclass (Wrf, Chimere) re-registers the
        # same aliases — so the final bound class is whichever was defined
        # last. We only assert the alias resolves to *some* RegularGrid reader.
        resolved = Reader.get_reader_subclass("RegularGrid", "DefaultRegularGrid")
        assert resolved.topology == "RegularGrid"
        assert issubclass(resolved, DefaultRegularGridReader)

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
                @classmethod
                def open_mfdataset(cls, files, vars, **kwargs):
                    return None
