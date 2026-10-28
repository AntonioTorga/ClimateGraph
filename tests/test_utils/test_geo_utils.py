"""Geographic maths: map-extent padding and grid spacing."""

import numpy as np
import pytest

from ClimateGraph.utils.geo_utils import pad_extent, step_metres


class TestPadExtent:
    def test_grows_each_axis_by_fraction_of_span(self):
        # span = 10 on both axes, 10% padding -> 1.0 on every side.
        lon_min, lon_max, lat_min, lat_max = pad_extent(-70, -60, -40, -30, 0.1)
        assert (lon_min, lon_max, lat_min, lat_max) == (-71.0, -59.0, -41.0, -29.0)

    def test_zero_padding_is_identity(self):
        assert pad_extent(-70, -60, -40, -30, 0.0) == (-70, -60, -40, -30)

    def test_zero_span_falls_back_to_fixed_pad(self):
        # A single point has zero span on both axes; fall back to +/-0.5.
        lon_min, lon_max, lat_min, lat_max = pad_extent(-70, -70, -40, -40, 0.05)
        assert (lon_min, lon_max, lat_min, lat_max) == (-70.5, -69.5, -40.5, -39.5)


class TestStepMetres:
    def test_degree_of_latitude_is_about_111_km(self):
        lon, lat = np.meshgrid(np.arange(4.0), np.arange(0.0, 4.0))
        _, ey = step_metres(lon, lat)
        assert ey.mean() == pytest.approx(111_195, rel=1e-3)

    def test_longitude_spacing_shrinks_with_latitude(self):
        # Why index space is not good enough: a degree of longitude is ~111 km
        # at the equator and ~79 km at 45 degrees.
        lon, lat = np.meshgrid(np.arange(4.0), np.array([0.0, 45.0, 60.0, 80.0]))
        ex, _ = step_metres(lon, lat)
        equator, mid, high = ex[0].mean(), ex[1].mean(), ex[3].mean()
        assert equator > mid > high
        assert mid / equator == pytest.approx(np.cos(np.deg2rad(45)), rel=1e-3)

    def test_handles_a_curvilinear_grid(self):
        # Latitude varying along x as well — the WRF/CHIMERE case.
        yy, xx = np.meshgrid(np.arange(5.0), np.arange(6.0), indexing="ij")
        lon = -71 + 0.1 * xx + 0.02 * yy
        lat = -33 + 0.1 * yy + 0.02 * xx
        ex, ey = step_metres(lon, lat)
        assert ex.shape == ey.shape == lon.shape
        assert np.all(ex > 0) and np.all(ey > 0)
