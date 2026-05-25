"""Unit tests for the small geometry helpers shared by the map plots
(``SpatialOverlay`` / ``SpatialMap``): auto-extent padding and NaN-obs drop.
"""

from __future__ import annotations

import numpy as np

from ClimateGraph.plot.plots import _drop_nan_points, _pad_extent


class TestPadExtent:
    def test_grows_each_axis_by_fraction_of_span(self):
        # span = 10 on both axes, 10% padding -> 1.0 on every side.
        lon_min, lon_max, lat_min, lat_max = _pad_extent(-70, -60, -40, -30, 0.1)
        assert (lon_min, lon_max, lat_min, lat_max) == (-71.0, -59.0, -41.0, -29.0)

    def test_zero_padding_is_identity(self):
        assert _pad_extent(-70, -60, -40, -30, 0.0) == (-70, -60, -40, -30)

    def test_zero_span_falls_back_to_fixed_pad(self):
        # A single point has zero span on both axes; fall back to ±0.5.
        lon_min, lon_max, lat_min, lat_max = _pad_extent(-70, -70, -40, -40, 0.05)
        assert (lon_min, lon_max, lat_min, lat_max) == (-70.5, -69.5, -40.5, -39.5)


class TestDropNanPoints:
    def test_drops_only_nan_valued_entries(self):
        lons = np.array([1.0, 2.0, 3.0])
        lats = np.array([10.0, 20.0, 30.0])
        vals = np.array([5.0, np.nan, 7.0])

        out_lons, out_lats, out_vals = _drop_nan_points(lons, lats, vals)

        assert out_lons.tolist() == [1.0, 3.0]
        assert out_lats.tolist() == [10.0, 30.0]
        assert out_vals.tolist() == [5.0, 7.0]

    def test_no_nans_returns_everything(self):
        lons, lats, vals = (np.array([1.0, 2.0]),) * 3
        out_lons, _, _ = _drop_nan_points(lons, lats, vals)
        assert out_lons.tolist() == [1.0, 2.0]

    def test_all_nan_returns_empty(self):
        lons = np.array([1.0, 2.0])
        lats = np.array([3.0, 4.0])
        vals = np.array([np.nan, np.nan])
        out_lons, out_lats, out_vals = _drop_nan_points(lons, lats, vals)
        assert out_lons.size == out_lats.size == out_vals.size == 0
