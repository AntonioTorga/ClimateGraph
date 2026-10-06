import numpy as np
from pyresample import kd_tree
from pyresample.geometry import SwathDefinition

from ClimateGraph.utils.resample_engine import PyresampleEngine, get_engine


def _geoms():
    ny, nx = 6, 8
    lat = np.linspace(-36, -33, ny)
    lon = np.linspace(-73, -69, nx)
    lon2d, lat2d = np.meshgrid(lon, lat)
    src = SwathDefinition(lons=lon2d, lats=lat2d)
    dlon = np.array([-72.0, -71.0, -70.0, -70.5, -71.5])
    dlat = np.array([-35.0, -34.0, -33.5, -34.5, -35.5])
    dst = SwathDefinition(lons=dlon, lats=dlat)
    return src, dst


class TestMakeResampler:
    def test_get_engine_returns_pyresample(self):
        assert isinstance(get_engine("pyresample"), PyresampleEngine)

    def test_2d_block_is_legacy_path(self):
        src, dst = _geoms()
        engine = PyresampleEngine()
        info = engine.prepare(src, dst, radius_of_influence=500_000)
        resampler = engine.make_resampler(info, dst.shape, src.shape)

        rng = np.random.default_rng(0)
        field = rng.normal(size=src.shape)
        out = resampler(field)
        assert out.shape == dst.shape  # (n_dst,)

    def test_batched_block_matches_per_slice(self):
        # A (k, *src) block must resample to (k, *dst) identical to k separate
        # single-slice calls.
        src, dst = _geoms()
        engine = PyresampleEngine()
        info = engine.prepare(src, dst, radius_of_influence=500_000)
        resampler = engine.make_resampler(info, dst.shape, src.shape)

        rng = np.random.default_rng(1)
        block = rng.normal(size=(4, *src.shape))  # (lead=4, y, x)
        batched = resampler(block)
        assert batched.shape == (4, *dst.shape)

        per_slice = np.stack([resampler(block[i]) for i in range(4)])
        np.testing.assert_allclose(batched, per_slice, equal_nan=True)

    def test_multiple_leading_dims(self):
        # (time, z, *src) -> (time, z, *dst).
        src, dst = _geoms()
        engine = PyresampleEngine()
        info = engine.prepare(src, dst, radius_of_influence=500_000)
        resampler = engine.make_resampler(info, dst.shape, src.shape)

        rng = np.random.default_rng(2)
        block = rng.normal(size=(3, 2, *src.shape))
        out = resampler(block)
        assert out.shape == (3, 2, *dst.shape)
        # Spot-check one (time, z) slice against a direct single call.
        direct = kd_tree.get_sample_from_neighbour_info(
            "nn", dst.shape, block[1, 0], *info, fill_value=np.nan
        )
        np.testing.assert_allclose(out[1, 0], direct, equal_nan=True)
