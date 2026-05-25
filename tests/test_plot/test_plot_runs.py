"""Fast end-to-end Plot.plot() smoke tests using in-memory data.

The config tests cover the Pydantic layer but never reach the bodies of
``plot()``, leaving plots.py at ~33% coverage. These tests drive each plot
class with the stub fixtures so the rendering path is actually executed --
the figures land in ``tmp_output_dir`` and are discarded.
"""

from __future__ import annotations

import matplotlib as mpl

mpl.use("Agg")

from ClimateGraph.plot.plots import (
    Scatter,
    ScatterConfig,
    SpatialMap,
    SpatialMapConfig,
    SpatialOverlay,
    SpatialOverlayConfig,
    TimeCycle,
    TimeCycleConfig,
    Timeseries,
    TimeSeriesConfig,
)
from ClimateGraph.utils.general_utils import CRSEnum

TIME_INTERVAL = "1/1/2019 - 6/1/2019"  # matches the 6-day fixture window


def _outputs(out_dir, name):
    return list((out_dir / name).iterdir())


class TestTimeseriesPlot:
    def test_runs_with_list_vars(self, regular_grid_data, tmp_output_dir):
        cfg = TimeSeriesConfig(
            type="timeseries",
            base="grid_stub",
            vars=["Temperatura"],
            time_interval=TIME_INTERVAL,
        )
        plot = Timeseries(
            name="ts_list",
            plot_config=cfg,
            data_registry={"grid_stub": regular_grid_data},
            domain_registry={},
            output_path=tmp_output_dir,
        )
        plot.plot()
        assert any(p.suffix == ".jpg" for p in _outputs(tmp_output_dir, "ts_list"))

    def test_runs_with_dict_vars_triggers_unit_conversion(
        self, regular_grid_data, tmp_output_dir
    ):
        # Dict form exercises the change_unit branch on the base dataset.
        cfg = TimeSeriesConfig(
            type="ts",
            base="grid_stub",
            vars={"Temperatura": "kelvin"},
            time_interval=TIME_INTERVAL,
        )
        plot = Timeseries(
            name="ts_dict",
            plot_config=cfg,
            data_registry={"grid_stub": regular_grid_data},
            domain_registry={},
            output_path=tmp_output_dir,
        )
        plot.plot()
        assert _outputs(tmp_output_dir, "ts_dict")

    def test_custom_filename_honored(self, regular_grid_data, tmp_output_dir):
        cfg = TimeSeriesConfig(
            type="ts",
            base="grid_stub",
            vars=["Temperatura"],
            time_interval=TIME_INTERVAL,
            filename="custom.jpg",
        )
        plot = Timeseries(
            name="ts_named",
            plot_config=cfg,
            data_registry={"grid_stub": regular_grid_data},
            domain_registry={},
            output_path=tmp_output_dir,
        )
        plot.plot()
        assert (tmp_output_dir / "ts_named" / "custom.jpg").exists()


class TestTimeCyclePlot:
    def test_runs_with_day_bucket(self, regular_grid_data, tmp_output_dir):
        cfg = TimeCycleConfig(
            type="cycle",
            base="grid_stub",
            vars=["Temperatura"],
            time_interval=TIME_INTERVAL,
            time_buckets="day",
        )
        plot = TimeCycle(
            name="tc",
            plot_config=cfg,
            data_registry={"grid_stub": regular_grid_data},
            domain_registry={},
            output_path=tmp_output_dir,
        )
        plot.plot()
        assert _outputs(tmp_output_dir, "tc")


class TestSpatialOverlayPlot:
    def test_runs_with_grid_and_point(
        self, regular_grid_data, point_surface_data, tmp_output_dir
    ):
        # SpatialOverlay accesses base.crs.crs (the class). The fixture sets
        # crs to a ccrs instance, so swap it for a CRSEnum that exposes that.
        regular_grid_data.crs = CRSEnum.platecarree
        point_surface_data.crs = CRSEnum.platecarree

        cfg = SpatialOverlayConfig(
            type="so",
            base="grid_stub",
            superposed="point_stub",
            time_interval=TIME_INTERVAL,
            vars=["Temperatura"],
        )
        plot = SpatialOverlay(
            name="so",
            plot_config=cfg,
            data_registry={
                "grid_stub": regular_grid_data,
                "point_stub": point_surface_data,
            },
            domain_registry={},
            output_path=tmp_output_dir,
        )
        plot.plot()
        assert _outputs(tmp_output_dir, "so")


class TestSpatialMapPlot:
    def test_runs_with_grid_contourf(self, regular_grid_data, tmp_output_dir):
        # RegularGrid takes the contourf branch.
        regular_grid_data.crs = CRSEnum.platecarree

        cfg = SpatialMapConfig(
            type="map",
            data="grid_stub",
            time_interval=TIME_INTERVAL,
            vars=["Temperatura"],
        )
        plot = SpatialMap(
            name="map_grid",
            plot_config=cfg,
            data_registry={"grid_stub": regular_grid_data},
            domain_registry={},
            output_path=tmp_output_dir,
        )
        plot.plot()
        assert _outputs(tmp_output_dir, "map_grid")

    def test_runs_with_point_scatter(self, point_surface_data, tmp_output_dir):
        # PointSurface takes the scatter branch.
        point_surface_data.crs = CRSEnum.platecarree

        cfg = SpatialMapConfig(
            type="spatial-map",
            data="point_stub",
            time_interval=TIME_INTERVAL,
            vars={"Temperatura": "kelvin"},
        )
        plot = SpatialMap(
            name="map_point",
            plot_config=cfg,
            data_registry={"point_stub": point_surface_data},
            domain_registry={},
            output_path=tmp_output_dir,
        )
        plot.plot()
        assert _outputs(tmp_output_dir, "map_point")

    def test_drop_nans_runs_with_empty_station(
        self, point_surface_data, tmp_output_dir
    ):
        # Blank out one station entirely so its reduced obs is NaN; drop_nans
        # should let the scatter branch render without it.
        point_surface_data.crs = CRSEnum.platecarree
        point_surface_data.obj["Temperatura"][:, 0] = float("nan")

        cfg = SpatialMapConfig(
            type="map",
            data="point_stub",
            time_interval=TIME_INTERVAL,
            vars=["Temperatura"],
            drop_nans=True,
        )
        plot = SpatialMap(
            name="map_drop",
            plot_config=cfg,
            data_registry={"point_stub": point_surface_data},
            domain_registry={},
            output_path=tmp_output_dir,
        )
        plot.plot()
        assert _outputs(tmp_output_dir, "map_drop")


class TestScatterPlot:
    def test_runs_with_grid_and_point(
        self, regular_grid_data, point_surface_data, tmp_output_dir
    ):
        # Scatter requires dict vars to drive its change_unit loop.
        cfg = ScatterConfig(
            type="scatter",
            base="grid_stub",
            other="point_stub",
            radius_of_influence=500_000,
            time_interval=TIME_INTERVAL,
            vars={"Temperatura": "kelvin"},
        )
        plot = Scatter(
            name="sc",
            plot_config=cfg,
            data_registry={
                "grid_stub": regular_grid_data,
                "point_stub": point_surface_data,
            },
            domain_registry={},
            output_path=tmp_output_dir,
        )
        plot.plot()
        assert _outputs(tmp_output_dir, "sc")
