"""Binning geometry and bin-boundary choice for the drawing code."""

from __future__ import annotations

import numpy as np
import pytest

from ClimateGraph.utils.general_utils import ReductionMethodEnum
from ClimateGraph.utils.plot_utils import bin_statistic, nice_edges


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
