import pytest

from ClimateGraph.data import Data, PointSurface, RegularGrid


class TestRegistry:
    def test_canonical_names_registered(self):
        assert Data.check_topology_type("RegularGrid")
        assert Data.check_topology_type("PointSurface")
        assert Data.check_topology_type("SatelliteSwath")

    def test_case_insensitive(self):
        assert Data.check_topology_type("regulargrid")
        assert Data.check_topology_type("REGULARGRID")

    def test_aliases_registered(self):
        assert Data.get_data_subclass("regular_grid") is RegularGrid
        assert Data.get_data_subclass("grid") is RegularGrid
        assert Data.get_data_subclass("point_surface") is PointSurface
        assert Data.get_data_subclass("pt_sfc") is PointSurface

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            Data.get_data_subclass("not-a-topology")

    def test_check_topology_unknown_is_false(self):
        assert Data.check_topology_type("not-a-topology") is False
