"""Primitive registry + config tests (the rendering-only building blocks)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ClimateGraph.plot.primitive import Primitive
from ClimateGraph.plot.primitives import (
    ContourFill,
    ContourFillConfig,
    Points,
    PointsConfig,
    Series,
    SeriesConfig,
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
