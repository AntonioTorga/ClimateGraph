"""Unit tests for the small helpers shared across plots: the map-plot geometry
helpers (auto-extent padding, NaN-obs drop) and the axis-decoration machinery
(reference-line positions, ``_decorate_axes`` / ``_finalize``).
"""

from __future__ import annotations

import matplotlib as mpl
import numpy as np

mpl.use("Agg")

import cartopy.crs as ccrs
import matplotlib.pyplot as plt

from ClimateGraph.plot.plot import _grid_positions
from ClimateGraph.plot.plots import (
    SpatialMapConfig,
    Timeseries,
    TimeSeriesConfig,
    _drop_nan_points,
    _pad_extent,
)


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


class TestGridPositions:
    def test_count_gives_exactly_n_interior_lines(self):
        # N lines evenly dividing the axis, none sitting on the spines.
        pos = _grid_positions(0, 10, 4)
        assert len(pos) == 4
        assert [round(p, 6) for p in pos] == [2.0, 4.0, 6.0, 8.0]

    def test_offset_shifts_by_fraction_of_spacing(self):
        # spacing = 10/(4+1) = 2, so offset 0.5 shifts every line by 1.0.
        pos = _grid_positions(0, 10, 4, offset=0.5)
        assert [round(p, 6) for p in pos] == [3.0, 5.0, 7.0, 9.0]

    def test_ticks_mode_uses_tick_locations(self):
        # Ticks on the spines (0, 10) are dropped so lines never overdraw the frame.
        pos = _grid_positions(0, 10, "ticks", tick_locs=[0, 2, 4, 6, 8, 10])
        assert [round(p, 6) for p in pos] == [2.0, 4.0, 6.0, 8.0]

    def test_ticks_mode_offset_lands_midway_between_ticks(self):
        # The "not over every tick" case: half a tick-gap shifts lines between them.
        pos = _grid_positions(0, 10, "ticks", offset=0.5, tick_locs=[0, 2, 4, 6, 8, 10])
        assert [round(p, 6) for p in pos] == [1.0, 3.0, 5.0, 7.0, 9.0]

    def test_offset_drops_positions_pushed_outside_the_axis(self):
        # A full-spacing shift pushes the last line onto/past the far spine.
        pos = _grid_positions(0, 10, 4, offset=1.0)
        assert [round(p, 6) for p in pos] == [4.0, 6.0, 8.0]

    def test_zero_or_negative_count_draws_nothing(self):
        assert _grid_positions(0, 10, 0) == []
        assert _grid_positions(0, 10, -3) == []


def _make_plot(tmp_output_dir, **config_kwargs):
    cfg = TimeSeriesConfig(type="ts", data="d", vars=["T"], **config_kwargs)
    return Timeseries(
        name="decor",
        plot_config=cfg,
        data_registry={},
        domain_registry={},
        output_path=tmp_output_dir,
    )


class TestDecorateAxes:
    def test_grid_count_draws_that_many_lines(self, tmp_output_dir):
        plot = _make_plot(tmp_output_dir, grid=4)
        figure = plt.figure()
        ax = figure.add_subplot(1, 1, 1)
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        before = len(ax.lines)

        plot._decorate_axes(figure)

        # 4 vertical + 4 horizontal reference lines.
        assert len(ax.lines) - before == 8
        plt.close(figure)

    def test_grid_only_decorates_the_named_axis(self, tmp_output_dir):
        plot = _make_plot(tmp_output_dir, grid={"x": 3})
        figure = plt.figure()
        ax = figure.add_subplot(1, 1, 1)
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)

        plot._decorate_axes(figure)

        assert len(ax.lines) == 3  # x only; y left clean
        plt.close(figure)

    def test_style_is_applied_to_the_lines(self, tmp_output_dir):
        plot = _make_plot(tmp_output_dir, grid={"x": 2, "color": "red", "alpha": 0.25})
        figure = plt.figure()
        ax = figure.add_subplot(1, 1, 1)
        ax.set_xlim(0, 10)

        plot._decorate_axes(figure)

        line = ax.lines[0]
        assert line.get_alpha() == 0.25
        assert line.get_linestyle() == "--"
        plt.close(figure)

    def test_named_ticks_are_applied(self, tmp_output_dir):
        plot = _make_plot(tmp_output_dir, xticks={0: "Surface", 5: "850 hPa"})
        figure = plt.figure()
        ax = figure.add_subplot(1, 1, 1)
        ax.set_xlim(0, 10)

        plot._decorate_axes(figure)

        assert [t.get_text() for t in ax.get_xticklabels()] == ["Surface", "850 hPa"]
        assert list(ax.get_xticks()) == [0.0, 5.0]
        plt.close(figure)

    def test_colorbar_axes_are_skipped(self, tmp_output_dir):
        plot = _make_plot(tmp_output_dir, grid=3)
        figure = plt.figure()
        ax = figure.add_subplot(1, 1, 1)
        mappable = ax.imshow(np.random.rand(4, 4))
        cbar = figure.colorbar(mappable, ax=ax)

        plot._decorate_axes(figure)

        # The colorbar's own axes must stay undecorated.
        assert len(cbar.ax.lines) == 0
        plt.close(figure)

    def test_geoaxes_uses_gridlines_without_raising(self, tmp_output_dir):
        # Map axes route through cartopy's graticule instead of axvline/axhline.
        plot = _make_plot(tmp_output_dir, grid=3)
        figure = plt.figure()
        ax = figure.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        ax.set_extent([-75, -68, -37, -32], crs=ccrs.PlateCarree())

        plot._decorate_axes(figure)  # must not raise

        assert len(ax.lines) == 0  # drawn as gridlines, not plain lines
        plt.close(figure)

    def test_no_config_is_a_no_op(self, tmp_output_dir):
        plot = _make_plot(tmp_output_dir)
        figure = plt.figure()
        ax = figure.add_subplot(1, 1, 1)

        plot._decorate_axes(figure)

        assert len(ax.lines) == 0
        plt.close(figure)


class TestFinalize:
    def test_decorates_and_writes(self, tmp_output_dir):
        # _finalize is the single post-render pipeline: decorate, then save.
        plot = _make_plot(tmp_output_dir, grid=3)
        figure = plt.figure()
        ax = figure.add_subplot(1, 1, 1)
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)

        plot._finalize(figure, "decorated.jpg")

        assert len(ax.lines) == 6  # 3 vertical + 3 horizontal
        assert (tmp_output_dir / "decor" / "decorated.jpg").exists()

    def test_map_config_also_carries_grid_fields(self, tmp_output_dir):
        # grid/xticks live on BasePlotConfig, so every plot type inherits them.
        cfg = SpatialMapConfig(type="map", data="d", vars=["T"], grid=5)
        assert cfg.grid.x == 5 and cfg.grid.y == 5
