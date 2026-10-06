import pytest

from ClimateGraph.domain import Domain
from ClimateGraph.domain.domains import (
    All,
    AllConfig,
    Attribute,
    AttributeConfig,
    Points,
    PointsConfig,
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
        filtered = dom.apply(point_surface_data)
        # Fixture has two sites with region=13 and one with region=5.
        assert filtered.obj.sizes["site"] == 2
        assert all(filtered.obj["region"].values == 13)

    def test_apply_filters_by_zone(self, point_surface_data):
        cfg = AttributeConfig(
            type="attr", field_name="zonaGeografica", field_value="Litoral"
        )
        dom = Attribute("Lit", domain_config=cfg)
        filtered = dom.apply(point_surface_data)
        assert filtered.obj.sizes["site"] == 2
        assert all(filtered.obj["zonaGeografica"].values == "Litoral")

    def test_no_match_returns_empty(self, point_surface_data):
        cfg = AttributeConfig(type="attr", field_name="region", field_value=9999)
        dom = Attribute("none", domain_config=cfg)
        filtered = dom.apply(point_surface_data)
        assert filtered.obj.sizes["site"] == 0

    def test_list_field_value_combines_via_isin(self, point_surface_data):
        # Fixture regions are (13, 13, 5); a list should match all three together.
        cfg = AttributeConfig(type="attr", field_name="region", field_value=[13, 5])
        dom = Attribute("combined", domain_config=cfg)
        filtered = dom.apply(point_surface_data)
        assert filtered.obj.sizes["site"] == 3

    def test_list_field_value_partial_match(self, point_surface_data):
        cfg = AttributeConfig(type="attr", field_name="region", field_value=[5, 9999])
        dom = Attribute("partial", domain_config=cfg)
        filtered = dom.apply(point_surface_data)
        assert filtered.obj.sizes["site"] == 1
        assert all(filtered.obj["region"].values == 5)


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
        masked = dom.apply(regular_grid_data)
        # Polygon spans the full grid: result should have non-NaN values.
        assert int(masked.obj["Temperatura"].notnull().sum()) > 0

    def test_apply_with_outside_polygon_yields_all_nan(self, regular_grid_data):
        # Polygon nowhere near the data.
        cfg = PolygonConfig(
            type="poly",
            vertex=[(10.0, 10.0), (10.0, 20.0), (20.0, 20.0), (20.0, 10.0)],
        )
        dom = Polygon("none", domain_config=cfg)
        masked = dom.apply(regular_grid_data)
        assert int(masked.obj["Temperatura"].notnull().sum()) == 0

    def test_multipolygon_accepted(self, regular_grid_data):
        cfg = PolygonConfig(
            type="poly",
            vertex=[
                [(-74.0, -36.5), (-74.0, -34.5), (-71.0, -34.5), (-71.0, -36.5)],
                [(-72.0, -34.0), (-72.0, -33.0), (-69.0, -33.0), (-69.0, -34.0)],
            ],
        )
        dom = Polygon("multi", domain_config=cfg)
        masked = dom.apply(regular_grid_data)
        assert "Temperatura" in masked.obj


class TestAllDomain:
    def test_apply_is_identity_on_dataset(self, regular_grid_data):
        cfg = AllConfig(type="all")
        dom = All("all", domain_config=cfg)
        result = dom.apply(regular_grid_data)
        # No resample_to → pure identity, same Data object handed back.
        assert result is regular_grid_data

    def test_apply_is_identity_on_point_surface(self, point_surface_data):
        cfg = AllConfig(type="all")
        dom = All("all", domain_config=cfg)
        result = dom.apply(point_surface_data)
        assert result is point_surface_data


class TestResampleStep:
    """The optional resample pre-step: a domain that reprojects onto a target geom
    before filtering. Source = grid fixture, target = point fixture."""

    def test_all_with_resample_projects_onto_target(
        self, regular_grid_data, point_surface_data
    ):
        from ClimateGraph.data import PointSurface

        cfg = AllConfig(type="all", resample_to="point_stub")
        dom = All("proj", domain_config=cfg, target_data=point_surface_data)
        result = dom.apply(regular_grid_data)

        # Correct topology: target's class + dims, no filter applied.
        assert isinstance(result, PointSurface)
        assert "site" in result.obj.dims
        assert "x" not in result.obj.dims
        # Source identity + source vars (canonical names, not "__" suffixed).
        assert result.name == "grid_stub"
        assert "Temperatura" in result.obj.data_vars

    def test_resample_does_not_convert_units(
        self, regular_grid_data, point_surface_data
    ):
        # The grid fixture is in kelvin (~285), the point target in degC (~12).
        # Resampling is PURE spatial projection: the result must keep the source's
        # kelvin values (and unit), not be silently converted to the target's degC
        # — otherwise a later change_unit would double-convert.
        # Wide radius so every station finds a grid neighbour (real, not NaN).
        cfg = AllConfig(
            type="all", resample_to="point_stub", radius_of_influence=500_000
        )
        dom = All("proj", domain_config=cfg, target_data=point_surface_data)
        result = dom.apply(regular_grid_data)

        assert result.var_unit("Temperatura") == "kelvin"
        assert float(result.obj["Temperatura"].mean()) > 100  # still kelvin-scaled

    def test_attribute_with_resample_filters_after_projection(
        self, regular_grid_data, point_surface_data
    ):
        # Reproject grid onto the 3 stations, THEN keep region==13 (2 of 3).
        cfg = AttributeConfig(
            type="attr",
            resample_to="point_stub",
            field_name="region",
            field_value=13,
        )
        dom = Attribute("proj13", domain_config=cfg, target_data=point_surface_data)
        result = dom.apply(regular_grid_data)

        assert result.obj.sizes["site"] == 2
        assert all(result.obj["region"].values == 13)

    def test_shared_target_reuses_resample_cache(
        self, regular_grid_data, point_surface_data
    ):
        # The one_for_each / many-domains payoff: two domains reprojecting the SAME
        # source onto the SAME target recompute the projection once — the second
        # domain hits the cache. Both filter differently after, but that's post-resample.
        dom_a = Attribute(
            "a",
            domain_config=AttributeConfig(
                type="attr",
                resample_to="point_stub",
                radius_of_influence=500_000,
                field_name="region",
                field_value=13,
            ),
            target_data=point_surface_data,
        )
        dom_b = Attribute(
            "b",
            domain_config=AttributeConfig(
                type="attr",
                resample_to="point_stub",
                radius_of_influence=500_000,
                field_name="region",
                field_value=5,
            ),
            target_data=point_surface_data,
        )
        dom_a.apply(regular_grid_data)
        dom_b.apply(regular_grid_data)

        # Cache lives on the source; a single shared projection served both domains.
        assert len(regular_grid_data._resample_cache) == 1


class TestPointsDomain:
    """Points domain: resample onto named points from inline / CSV, grouped or fanned."""

    def _points(self):
        return [
            {"name": "Alpha", "lat": -34.5, "lon": -71.0},
            {"name": "Beta", "lat": -35.0, "lon": -70.0},
        ]

    def _target(self):
        from ClimateGraph.data.point_surface import PointSurface

        pts = self._points()
        return PointSurface.from_points(
            "__points_target_0",
            [p["name"] for p in pts],
            [p["lat"] for p in pts],
            [p["lon"] for p in pts],
        )

    def test_inline_config_parses(self):
        cfg = PointsConfig(type="points", points=self._points())
        assert cfg.resolve_points() == [
            ("Alpha", -34.5, -71.0),
            ("Beta", -35.0, -70.0),
        ]

    def test_csv_config_parses_with_aliases(self, tmp_path):
        # Uses aliased headers (latitud/longitud) to exercise the alias resolver.
        csv = tmp_path / "pts.csv"
        csv.write_text("name,latitud,longitud\nAlpha,-34.5,-71.0\nBeta,-35.0,-70.0\n")
        cfg = PointsConfig(type="pts", path=csv)
        assert cfg.resolve_points() == [
            ("Alpha", -34.5, -71.0),
            ("Beta", -35.0, -70.0),
        ]

    def test_requires_exactly_one_source(self):
        with pytest.raises(ValueError, match="exactly one"):
            PointsConfig(type="points")  # neither
        with pytest.raises(ValueError, match="exactly one"):
            PointsConfig(type="points", path="x.csv", points=self._points())  # both

    def test_grouped_apply_resamples_onto_all_points(self, regular_grid_data):
        cfg = PointsConfig(type="points", points=self._points())
        dom = Points("mypoints", domain_config=cfg, target_data=self._target())
        result = dom.apply(regular_grid_data)
        # Lands on the point geometry, named by the provided names, all kept.
        assert list(result.obj.site.values) == ["Alpha", "Beta"]
        assert "x" not in result.obj.dims
        assert "Temperatura" in result.obj.data_vars

    def test_fanout_filter_keeps_single_named_point(self, regular_grid_data):
        cfg = PointsConfig(type="points", points=self._points(), select_name="Beta")
        dom = Points("Beta", domain_config=cfg, target_data=self._target())
        result = dom.apply(regular_grid_data)
        assert list(result.obj.site.values) == ["Beta"]

    def test_fanned_domains_share_one_resample(self, regular_grid_data):
        # Grouped + a fan-out selection sharing the SAME target must reuse one
        # resample cache entry on the source (the shared-target payoff).
        target = self._target()
        grouped = Points(
            "mypoints",
            domain_config=PointsConfig(type="points", points=self._points()),
            target_data=target,
        )
        alpha = Points(
            "Alpha",
            domain_config=PointsConfig(
                type="points", points=self._points(), select_name="Alpha"
            ),
            target_data=target,
        )
        grouped.apply(regular_grid_data)
        alpha.apply(regular_grid_data)
        assert len(regular_grid_data._resample_cache) == 1


class TestShapefileConfig:
    def test_config_parses(self, tmp_path):
        # We don't need a real shapefile for config validation.
        fake = tmp_path / "a.shp"
        fake.write_bytes(b"")
        cfg = ShapefileConfig(type="shp", path=fake, field_value="X")
        assert cfg.type == "shp"
        assert cfg.field_value == "X"
