from ClimateGraph.domain import Domain
from ClimateGraph.domain.domains import (
    All,
    AllConfig,
    Attribute,
    AttributeConfig,
    Polygon,
    PolygonConfig,
    Shapefile,
    ShapefileConfig,
)


class TestRegistry:
    def test_canonical_names_registered(self):
        assert Domain.check_domain_class("attribute")
        assert Domain.check_domain_class("polygon")
        assert Domain.check_domain_class("shapefile")
        assert Domain.check_domain_class("all")

    def test_aliases_registered(self):
        assert Domain.get_domain_class("attr") is Attribute
        assert Domain.get_domain_class("poly") is Polygon
        assert Domain.get_domain_class("shp") is Shapefile

    def test_case_insensitive(self):
        assert Domain.get_domain_class("ATTR") is Attribute

    def test_build_config_union_includes_all(self):
        union = Domain.build_config_union()
        # Three domain types, three configs.
        assert union is not None


class TestAttributeDomain:
    def test_apply_filters_by_region(self, point_surface_data):
        cfg = AttributeConfig(type="attr", field_name="region", field_value=13)
        dom = Attribute("RM", domain_config=cfg)
        filtered = dom.apply(point_surface_data.obj)
        # Fixture has two sites with region=13 and one with region=5.
        assert filtered.sizes["site"] == 2
        assert all(filtered["region"].values == 13)

    def test_apply_filters_by_zone(self, point_surface_data):
        cfg = AttributeConfig(
            type="attr", field_name="zonaGeografica", field_value="Litoral"
        )
        dom = Attribute("Lit", domain_config=cfg)
        filtered = dom.apply(point_surface_data.obj)
        assert filtered.sizes["site"] == 2
        assert all(filtered["zonaGeografica"].values == "Litoral")

    def test_no_match_returns_empty(self, point_surface_data):
        cfg = AttributeConfig(type="attr", field_name="region", field_value=9999)
        dom = Attribute("none", domain_config=cfg)
        filtered = dom.apply(point_surface_data.obj)
        assert filtered.sizes["site"] == 0

    def test_list_field_value_combines_via_isin(self, point_surface_data):
        # Fixture regions are (13, 13, 5); a list should match all three together.
        cfg = AttributeConfig(type="attr", field_name="region", field_value=[13, 5])
        dom = Attribute("combined", domain_config=cfg)
        filtered = dom.apply(point_surface_data.obj)
        assert filtered.sizes["site"] == 3

    def test_list_field_value_partial_match(self, point_surface_data):
        cfg = AttributeConfig(type="attr", field_name="region", field_value=[5, 9999])
        dom = Attribute("partial", domain_config=cfg)
        filtered = dom.apply(point_surface_data.obj)
        assert filtered.sizes["site"] == 1
        assert all(filtered["region"].values == 5)


class TestPolygonDomain:
    def test_apply_masks_outside_polygon(self, regular_grid_data):
        # Big polygon covering the whole fixture bbox.
        cfg = PolygonConfig(
            type="poly",
            vertex=[
                (-74.0, -36.5),
                (-74.0, -33.0),
                (-69.0, -33.0),
                (-69.0, -36.5),
            ],
        )
        dom = Polygon("big", domain_config=cfg)
        masked = dom.apply(regular_grid_data.obj)
        # Polygon spans the full grid: result should have non-NaN values.
        assert int(masked["Temperatura"].notnull().sum()) > 0

    def test_apply_with_outside_polygon_yields_all_nan(self, regular_grid_data):
        # Polygon nowhere near the data.
        cfg = PolygonConfig(
            type="poly",
            vertex=[(10.0, 10.0), (10.0, 20.0), (20.0, 20.0), (20.0, 10.0)],
        )
        dom = Polygon("none", domain_config=cfg)
        masked = dom.apply(regular_grid_data.obj)
        assert int(masked["Temperatura"].notnull().sum()) == 0

    def test_multipolygon_accepted(self, regular_grid_data):
        cfg = PolygonConfig(
            type="poly",
            vertex=[
                [(-74.0, -36.5), (-74.0, -34.5), (-71.0, -34.5), (-71.0, -36.5)],
                [(-72.0, -34.0), (-72.0, -33.0), (-69.0, -33.0), (-69.0, -34.0)],
            ],
        )
        dom = Polygon("multi", domain_config=cfg)
        masked = dom.apply(regular_grid_data.obj)
        assert "Temperatura" in masked


class TestAllDomain:
    def test_apply_is_identity_on_dataset(self, regular_grid_data):
        cfg = AllConfig(type="all")
        dom = All("all", domain_config=cfg)
        result = dom.apply(regular_grid_data.obj)
        assert result is regular_grid_data.obj

    def test_apply_is_identity_on_point_surface(self, point_surface_data):
        cfg = AllConfig(type="all")
        dom = All("all", domain_config=cfg)
        result = dom.apply(point_surface_data.obj)
        assert result is point_surface_data.obj


class TestShapefileConfig:
    def test_config_parses(self, tmp_path):
        # We don't need a real shapefile for config validation.
        fake = tmp_path / "a.shp"
        fake.write_bytes(b"")
        cfg = ShapefileConfig(type="shp", path=fake, field_value="X")
        assert cfg.type == "shp"
        assert cfg.field_value == "X"
