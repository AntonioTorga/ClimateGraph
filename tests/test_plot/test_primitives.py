"""Primitive registry + config tests (the rendering-only building blocks)."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from ClimateGraph.plot.primitive import Primitive
from ClimateGraph.plot.primitives import (
    Arrows,
    ArrowsConfig,
    Contour,
    ContourConfig,
    ContourFill,
    ContourFillConfig,
    Gradient,
    GradientConfig,
    Points,
    PointsConfig,
    Raster,
    RasterConfig,
    Series,
    SeriesConfig,
    _step_metres,
)


class TestPrimitiveRegistry:
    def test_canonical_names_registered(self):
        assert Primitive.get_primitive_class("series") is Series
        assert Primitive.get_primitive_class("contourf") is ContourFill
        assert Primitive.get_primitive_class("points") is Points

    def test_aliases_registered(self):
        assert Primitive.get_primitive_class("line") is Series
        assert Primitive.get_primitive_class("contour_fill") is ContourFill
        assert Primitive.get_primitive_class("contourfill") is ContourFill
        assert Primitive.get_primitive_class("scatter") is Points

    def test_check_primitive_class(self):
        assert Primitive.check_primitive_class("series") is True
        assert Primitive.check_primitive_class("nope") is False

    def test_colorbar_and_legend_flags(self):
        # Lines go in a legend; contourf / coloured scatter get a colorbar.
        assert Series.wants_legend is True and Series.wants_colorbar is False
        assert ContourFill.wants_colorbar is True
        assert Points.wants_colorbar is True


class TestPrimitiveConfigs:
    def test_series_defaults_and_required_x(self):
        cfg = SeriesConfig(type="series", dataset="d", x="time")
        assert cfg.reduction_method.value == "mean"
        assert cfg.var is None and cfg.unit is None

    def test_series_missing_x_rejected(self):
        with pytest.raises(ValidationError):
            SeriesConfig(type="series", dataset="d")

    def test_contourf_defaults(self):
        cfg = ContourFillConfig(type="contourf", dataset="d", x="lon", y="lat")
        assert cfg.levels == 10
        assert cfg.cmap == "viridis"

    def test_contourf_requires_both_axes(self):
        with pytest.raises(ValidationError):
            ContourFillConfig(type="contourf", dataset="d", x="lon")  # missing y

    def test_points_defaults(self):
        cfg = PointsConfig(type="points", dataset="d", x="lon", y="lat")
        assert cfg.markersize == 40.0
        assert cfg.edgecolor == "k"
        assert cfg.drop_nans is False

    def test_styling_flows_through_model_extra(self):
        # Unknown keys (color, linewidth) ride along for the matplotlib call.
        cfg = SeriesConfig(
            type="line", dataset="d", x="time", color="black", linewidth=2
        )
        assert cfg.model_extra == {"color": "black", "linewidth": 2}
        prim = Series("p", cfg)
        assert prim.style == {"color": "black", "linewidth": 2}

    def test_contour_defaults(self):
        cfg = ContourConfig(type="contour", dataset="d", x="lon", y="lat")
        assert cfg.levels == 10
        assert cfg.colors == "black"
        assert cfg.clabel is True

    def test_contour_requires_both_axes(self):
        with pytest.raises(ValidationError):
            ContourConfig(type="contour", dataset="d", x="lon")  # missing y

    def test_raster_defaults(self):
        cfg = RasterConfig(type="raster", dataset="d", x="lon", y="lat")
        assert cfg.cmap == "viridis"
        assert cfg.vmin is None and cfg.vmax is None

    def test_raster_declares_no_shading(self):
        # xarray's pcolormesh already infers cell edges from the coordinates;
        # a shading field here would fight that inference, not configure it.
        assert "shading" not in RasterConfig.model_fields


class TestNewPrimitiveRegistration:
    def test_contour_and_raster_registered(self):
        assert Primitive.get_primitive_class("contour") is Contour
        assert Primitive.get_primitive_class("contour_lines") is Contour
        assert Primitive.get_primitive_class("raster") is Raster
        assert Primitive.get_primitive_class("pcolormesh") is Raster
        assert Primitive.get_primitive_class("mesh") is Raster

    def test_contour_does_not_claim_the_colour_scale(self):
        # Single-coloured by design: its values ride on inline labels, leaving
        # the figure's one colorbar for whatever is drawn underneath.
        assert Contour.wants_colorbar is False
        assert Raster.wants_colorbar is True

    def test_contour_is_distinct_from_contourf(self):
        assert Primitive.get_primitive_class("contourf") is ContourFill
        assert Contour is not ContourFill

    def test_arrow_primitives_registered(self):
        assert Primitive.get_primitive_class("gradient") is Gradient
        assert Primitive.get_primitive_class("grad") is Gradient
        assert Primitive.get_primitive_class("arrows") is Arrows
        assert Primitive.get_primitive_class("quiver") is Arrows

    def test_arrows_are_single_coloured(self):
        # Length already carries magnitude; colouring it too would spend the
        # figure's one colour scale on information already shown.
        assert Arrows.wants_colorbar is False
        assert Gradient.wants_colorbar is False


class TestArrowsConfig:
    def test_components_pair_accepted(self):
        cfg = ArrowsConfig(type="arrows", dataset="d", x="lon", y="lat", u="u10", v="v10")
        assert Arrows.required_vars(cfg) == {"u": "u10", "v": "v10"}

    def test_polar_pair_accepted(self):
        cfg = ArrowsConfig(
            type="arrows", dataset="d", x="lon", y="lat", speed="ws", direction="wd"
        )
        assert Arrows.required_vars(cfg) == {"speed": "ws", "direction": "wd"}

    def test_both_spellings_rejected(self):
        with pytest.raises(ValidationError, match="not both"):
            ArrowsConfig(
                type="arrows",
                dataset="d",
                x="lon",
                y="lat",
                u="u10",
                v="v10",
                speed="ws",
                direction="wd",
            )

    def test_neither_pair_rejected(self):
        with pytest.raises(ValidationError, match="complete pair"):
            ArrowsConfig(type="arrows", dataset="d", x="lon", y="lat")

    def test_half_a_pair_rejected(self):
        with pytest.raises(ValidationError, match="complete pair"):
            ArrowsConfig(type="arrows", dataset="d", x="lon", y="lat", u="u10")

    def test_single_variable_primitives_declare_no_roles(self):
        cfg = SeriesConfig(type="series", dataset="d", x="time")
        assert Series.required_vars(cfg) == {}


class TestGradientConfig:
    def test_defaults(self):
        cfg = GradientConfig(type="gradient", dataset="d", x="lon", y="lat")
        assert cfg.thin == 1
        assert cfg.normalize is False
        assert cfg.descending is False

    def test_needs_no_second_variable(self):
        # The field is the one already being drawn.
        cfg = GradientConfig(type="gradient", dataset="d", x="lon", y="lat")
        assert Gradient.required_vars(cfg) == {}


class TestStepMetres:
    def test_degree_of_latitude_is_about_111_km(self):
        lon, lat = np.meshgrid(np.arange(4.0), np.arange(0.0, 4.0))
        _, ey = _step_metres(lon, lat)
        assert ey.mean() == pytest.approx(111_195, rel=1e-3)

    def test_longitude_spacing_shrinks_with_latitude(self):
        # The reason index space is not good enough: a degree of longitude is
        # ~111 km at the equator and ~79 km at 45 degrees.
        lon, lat = np.meshgrid(np.arange(4.0), np.array([0.0, 45.0, 60.0, 80.0]))
        ex, _ = _step_metres(lon, lat)
        equator, mid, high = ex[0].mean(), ex[1].mean(), ex[3].mean()
        assert equator > mid > high
        assert mid / equator == pytest.approx(np.cos(np.deg2rad(45)), rel=1e-3)

    def test_handles_a_curvilinear_grid(self):
        # Latitude varying along x as well — the WRF/CHIMERE case.
        yy, xx = np.meshgrid(np.arange(5.0), np.arange(6.0), indexing="ij")
        lon = -71 + 0.1 * xx + 0.02 * yy
        lat = -33 + 0.1 * yy + 0.02 * xx
        ex, ey = _step_metres(lon, lat)
        assert ex.shape == ey.shape == lon.shape
        assert np.all(ex > 0) and np.all(ey > 0)
