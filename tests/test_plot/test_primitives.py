"""Primitive registry + config tests (the rendering-only building blocks)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ClimateGraph.plot.primitive import Primitive
from ClimateGraph.plot.primitives import (
    Arrows,
    ArrowsConfig,
    Band,
    BandConfig,
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
    Rose,
    RoseConfig,
    Series,
    SeriesConfig,
)
from ClimateGraph.utils.general_utils import ReductionMethodEnum


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
        cfg = ArrowsConfig(
            type="arrows", dataset="d", x="lon", y="lat", u="u10", v="v10"
        )
        assert Arrows.required_vars(cfg) == {"u": ("d", "u10"), "v": ("d", "v10")}

    def test_polar_pair_accepted(self):
        cfg = ArrowsConfig(
            type="arrows", dataset="d", x="lon", y="lat", speed="ws", direction="wd"
        )
        assert Arrows.required_vars(cfg) == {
            "speed": ("d", "ws"),
            "direction": ("d", "wd"),
        }

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


class TestRoseConfig:
    def test_binning_variables_and_the_plot_var_become_roles(self):
        cfg = RoseConfig(type="rose", dataset="d", angle="WD", radius="WS")
        assert Rose.required_vars(cfg, "PM25") == {
            "angle": ("d", "WD"),
            "radius": ("d", "WS"),
            "value": ("d", "PM25"),
        }

    def test_colour_role_absent_without_a_variable(self):
        # No variable means the cells are coloured by sample count.
        cfg = RoseConfig(type="rose", dataset="d", angle="WD", radius="WS")
        assert Rose.required_vars(cfg) == {"angle": ("d", "WD"), "radius": ("d", "WS")}

    def test_needs_no_coordinates(self):
        # Both axes come from variables, so there is nothing to bind x/y to.
        cfg = RoseConfig(type="rose", dataset="d", angle="WD", radius="WS")
        assert cfg.x is None and cfg.y is None
        assert Rose.required_coords == frozenset()

    def test_keeps_every_sample(self):
        assert Rose.reduces_to_axes is False

    def test_declares_polar_axes(self):
        assert Rose.requires_projection == "polar"
        assert RoseConfig.requires_projection == "polar"

    def test_defaults(self):
        cfg = RoseConfig(type="rose", dataset="d", angle="WD", radius="WS")
        assert cfg.angle_period == 360.0
        assert cfg.angle_bins == 16
        assert cfg.radius_bins == 6
        assert cfg.levels == 5
        assert cfg.statistic is ReductionMethodEnum.mean
        assert cfg.min_count == 1

    def test_explicit_radius_edges_accepted(self):
        cfg = RoseConfig(
            type="rose", dataset="d", angle="WD", radius="WS", radius_bins=[0, 2, 5]
        )
        assert cfg.radius_bins == [0, 2, 5]

    def test_colour_classes_go_in_a_legend(self):
        # The cells hold a handful of classes, which a legend names outright.
        assert Rose.wants_colorbar is False

    def test_aliases_registered(self):
        assert Primitive.get_primitive_class("rose") is Rose
        assert Primitive.get_primitive_class("windrose") is Rose
        assert Primitive.get_primitive_class("polar_bin") is Rose


class TestBandConfig:
    def test_explicit_edges(self):
        cfg = BandConfig(type="band", dataset="d", x="time", lower="lo", upper="hi")
        assert Band.required_vars(cfg) == {
            "lower": ("d", "lo"),
            "upper": ("d", "hi"),
        }

    def test_edges_may_each_name_their_own_dataset(self):
        # The case a single `dataset:` cannot express.
        cfg = BandConfig(type="band", x="time", lower="OBS::PM25", upper="MODEL::PM25")
        assert Band.required_vars(cfg) == {
            "lower": ("OBS", "PM25"),
            "upper": ("MODEL", "PM25"),
        }

    def test_spread_takes_the_plot_variable(self):
        cfg = BandConfig(type="band", dataset="d", x="time", spread="std")
        assert Band.required_vars(cfg, "PM25") == {"value": ("d", "PM25")}

    def test_both_spellings_rejected(self):
        with pytest.raises(ValidationError, match="not both"):
            BandConfig(
                type="band", dataset="d", x="time", lower="lo", upper="hi", spread="std"
            )

    def test_half_a_pair_rejected(self):
        with pytest.raises(ValidationError, match="both 'lower' and 'upper'"):
            BandConfig(type="band", dataset="d", x="time", lower="lo")

    def test_neither_spelling_rejected(self):
        with pytest.raises(ValidationError, match="or 'spread'"):
            BandConfig(type="band", dataset="d", x="time")

    def test_defaults(self):
        cfg = BandConfig(type="band", dataset="d", x="time", spread="minmax")
        assert (cfg.k, cfg.alpha) == (1.0, 0.3)

    def test_keeps_every_sample(self):
        # The spread lives in the dims a reduction would have collapsed.
        assert Band.reduces_to_axes is False

    def test_aliases_registered(self):
        assert Primitive.get_primitive_class("band") is Band
        assert Primitive.get_primitive_class("fill_between") is Band
        assert Primitive.get_primitive_class("envelope") is Band


class TestQualifiedVarRefs:
    def test_a_qualified_var_folds_into_the_two_fields(self):
        cfg = SeriesConfig(type="series", x="time", var="MODEL::PM25")
        assert (cfg.dataset, cfg.var) == ("MODEL", "PM25")

    def test_it_overrides_the_subplot_dataset(self):
        cfg = SeriesConfig(type="series", dataset="OBS", x="time", var="MODEL::PM25")
        assert (cfg.dataset, cfg.var) == ("MODEL", "PM25")

    def test_a_bare_var_keeps_the_subplot_dataset(self):
        cfg = SeriesConfig(type="series", dataset="OBS", x="time", var="PM25")
        assert (cfg.dataset, cfg.var) == ("OBS", "PM25")

    def test_a_layer_naming_no_dataset_at_all_is_rejected(self):
        with pytest.raises(ValidationError, match="DATASET::VAR"):
            SeriesConfig(type="series", x="time", var="PM25")

    def test_a_role_naming_no_dataset_is_rejected(self):
        with pytest.raises(ValidationError, match="name no dataset"):
            BandConfig(type="band", x="time", lower="lo", upper="MODEL::hi")
