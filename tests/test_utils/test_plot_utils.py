"""Binning geometry, bin-boundary choice and output naming."""

from __future__ import annotations

import numpy as np
import pytest

from ClimateGraph.utils.general_utils import ReductionMethodEnum
from ClimateGraph.utils.plot_utils import (
    bin_statistic,
    compose_filename,
    nice_edges,
)


class TestNiceEdges:
    def test_rounds_to_readable_boundaries(self):
        assert list(nice_edges(0.0, 3.4921, 5)) == [0.0, 1.0, 2.0, 3.0, 4.0]

    def test_covers_the_whole_span(self):
        edges = nice_edges(-2.0, 11.0, 5)
        assert edges[0] <= -2.0 and edges[-1] >= 11.0

    def test_count_is_an_upper_bound(self):
        assert len(nice_edges(0.0, 3.4921, 5)) - 1 <= 5

    def test_scales_to_small_and_large_spans(self):
        assert nice_edges(0.0, 0.84, 5) == pytest.approx([0, 0.2, 0.4, 0.6, 0.8, 1])
        assert nice_edges(0.0, 37.0, 5) == pytest.approx([0, 10, 20, 30, 40])

    @pytest.mark.parametrize(
        ("lo", "hi"),
        [(np.nan, 1.0), (0.0, np.nan), (np.inf, 1.0), (5.0, 5.0)],
    )
    def test_degenerate_spans_fall_back_to_a_unit_range(self, lo, hi):
        assert list(nice_edges(lo, hi, 5)) == [0.0, 1.0]


class TestBinStatistic:
    #           NE quadrant        SW quadrant
    THETA = np.array([0.5, 0.6, 0.7, 4.0, 4.1])
    RADIUS = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
    T_EDGES = np.linspace(0, 2 * np.pi, 4 + 1)
    R_EDGES = np.array([0.0, 2.0])

    def _grid(self, values, statistic=ReductionMethodEnum.mean, min_count=1):
        return bin_statistic(
            self.THETA,
            self.RADIUS,
            values,
            self.T_EDGES,
            self.R_EDGES,
            statistic,
            min_count,
        )

    def test_counts_when_no_values_are_given(self):
        grid = self._grid(None)
        assert grid[0, 0] == 3
        assert grid[2, 0] == 2
        assert np.isnan(grid[1, 0])

    def test_mean_of_each_cell(self):
        grid = self._grid(np.array([10.0, 20.0, 30.0, 4.0, 6.0]))
        assert grid[0, 0] == pytest.approx(20.0)
        assert grid[2, 0] == pytest.approx(5.0)

    def test_min_and_max_of_each_cell(self):
        values = np.array([10.0, 20.0, 30.0, 4.0, 6.0])
        assert self._grid(values, ReductionMethodEnum.min)[0, 0] == 10.0
        assert self._grid(values, ReductionMethodEnum.max)[0, 0] == 30.0

    def test_min_count_blanks_thin_cells(self):
        grid = self._grid(np.array([10.0, 20.0, 30.0, 4.0, 6.0]), min_count=3)
        assert grid[0, 0] == pytest.approx(20.0)
        assert np.isnan(grid[2, 0])

    def test_nan_samples_are_dropped(self):
        grid = self._grid(np.array([10.0, 20.0, np.nan, 4.0, 6.0]))
        assert grid[0, 0] == pytest.approx(15.0)

    def test_samples_on_the_last_radius_edge_are_kept(self):
        grid = bin_statistic(
            np.array([0.5]),
            np.array([2.0]),
            np.array([7.0]),
            self.T_EDGES,
            self.R_EDGES,
            ReductionMethodEnum.max,
            1,
        )
        assert grid[0, 0] == 7.0


class TestComposeFilename:
    TOKENS = {"time": "01-06-2021", "domain": "centro", "var": "PM25"}

    def test_a_plain_stem_with_no_fan_out_is_kept_as_written(self):
        assert compose_filename("mychart", self.TOKENS, [], "png") == "mychart.png"

    def test_a_plain_stem_gains_every_active_axis(self):
        # Without this, N figures would write one path and only the last
        # would survive.
        out = compose_filename("mychart", self.TOKENS, ["time", "var"], "png")
        assert out == "mychart-01-06-2021-PM25.png"

    def test_a_template_is_formatted(self):
        out = compose_filename("{var}_{domain}", self.TOKENS, [], "png")
        assert out == "PM25_centro.png"

    def test_a_template_only_gains_the_axes_it_omits(self):
        out = compose_filename("{var}", self.TOKENS, ["time", "var"], "png")
        assert out == "PM25-01-06-2021.png"

    def test_a_template_naming_every_active_axis_gains_nothing(self):
        out = compose_filename("{var}-{time}", self.TOKENS, ["time", "var"], "png")
        assert out == "PM25-01-06-2021.png"

    def test_subdirectories_survive(self):
        out = compose_filename("{var}/{domain}", self.TOKENS, [], "png")
        assert out == "PM25/centro.png"

    def test_an_extension_is_not_doubled(self):
        assert compose_filename("named.png", self.TOKENS, [], "png") == "named.png"

    def test_a_different_extension_is_kept_and_the_format_appended(self):
        # The stem is the user's; only a matching suffix is absorbed.
        assert compose_filename("v1.2", self.TOKENS, [], "png") == "v1.2.png"
