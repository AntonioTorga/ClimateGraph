import pytest

from ClimateGraph.plot import Plot
from ClimateGraph.plot.plots import Scatter, SpatialOverlay, TimeCycle, Timeseries


class TestRegistry:
    def test_canonical_class_names(self):
        assert Plot.get_plot_class("timeseries") is Timeseries
        assert Plot.get_plot_class("scatter") is Scatter
        assert Plot.get_plot_class("spatialoverlay") is SpatialOverlay
        assert Plot.get_plot_class("timecycle") is TimeCycle

    def test_timeseries_aliases(self):
        assert Plot.get_plot_class("ts") is Timeseries
        assert Plot.get_plot_class("time-series") is Timeseries

    def test_scatter_alias(self):
        assert Plot.get_plot_class("sc") is Scatter

    def test_spatialoverlay_aliases(self):
        assert Plot.get_plot_class("spatial-overlay") is SpatialOverlay
        assert Plot.get_plot_class("so") is SpatialOverlay

    def test_timecycle_aliases(self):
        assert Plot.get_plot_class("cycle") is TimeCycle
        assert Plot.get_plot_class("time cycle") is TimeCycle

    def test_check_plot_class(self):
        assert Plot.check_plot_class("ts") is True
        assert Plot.check_plot_class("nope") is False
