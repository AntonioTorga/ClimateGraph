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
            data="grid_stub",
            vars=["Temperatura"],
            time=TIME_INTERVAL,
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
        # Dict form exercises the change_unit branch on the dataset.
        cfg = TimeSeriesConfig(
            type="ts",
            data="grid_stub",
            vars={"Temperatura": "kelvin"},
            time=TIME_INTERVAL,
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
            data="grid_stub",
            vars=["Temperatura"],
            time=TIME_INTERVAL,
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

    def test_list_time_produces_one_output_per_entry(
        self, regular_grid_data, tmp_output_dir
    ):
        # Fixture spans 2019-01-01..06; split into two non-overlapping windows.
        cfg = TimeSeriesConfig(
            type="ts",
            data="grid_stub",
            vars=["Temperatura"],
            time=["1/1/2019 - 3/1/2019", "4/1/2019 - 6/1/2019"],
        )
        plot = Timeseries(
            name="ts_multi_time",
            plot_config=cfg,
            data_registry={"grid_stub": regular_grid_data},
            domain_registry={},
            output_path=tmp_output_dir,
        )
        plot.plot()
        outputs = _outputs(tmp_output_dir, "ts_multi_time")
        assert len(outputs) == 2
        names = {p.name for p in outputs}
        assert any("01-01-2019_03-01-2019" in n for n in names)
        assert any("04-01-2019_06-01-2019" in n for n in names)

    def test_resample_domain_in_timeseries(
        self, regular_grid_data, point_surface_data, tmp_output_dir
    ):
        # 12b payoff: a resample_to domain (grid -> stations) used in a NAMED plot
        # used to crash (KeyError Temperatura__...) because the plot resampled
        # internally first. Now the domain applies to raw Data, so it just works.
        from ClimateGraph.domain.domains import Attribute, AttributeConfig

        cfg = AttributeConfig(
            type="attr",
            resample_to="point_stub",
            radius_of_influence=500_000,
            field_name="region",
            field_value=13,
        )
        dom = Attribute(
            "at_stations", domain_config=cfg, target_data=point_surface_data
        )

        plot_cfg = TimeSeriesConfig(
            type="ts",
            data=["point_stub", "grid_stub"],  # stations + grid-sampled-at-stations
            domains=["at_stations"],
            vars=["Temperatura"],
            time=TIME_INTERVAL,
        )
        plot = Timeseries(
            name="ts_resampled",
            plot_config=plot_cfg,
            data_registry={
                "grid_stub": regular_grid_data,
                "point_stub": point_surface_data,
            },
            domain_registry={"at_stations": dom},
            output_path=tmp_output_dir,
        )
        plot.plot()  # must not raise
        assert _outputs(tmp_output_dir, "ts_resampled")


class TestTimeCyclePlot:
    def test_runs_with_day_bucket(self, regular_grid_data, tmp_output_dir):
        cfg = TimeCycleConfig(
            type="cycle",
            data="grid_stub",
            vars=["Temperatura"],
            time=TIME_INTERVAL,
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

    def test_std_band_only_for_base_and_title_reflects_bucket(
        self, regular_grid_data, point_surface_data, tmp_output_dir, monkeypatch
    ):
        import matplotlib.axes
        import matplotlib.figure

        fills: list[int] = []
        titles: list[str] = []
        monkeypatch.setattr(
            matplotlib.axes.Axes,
            "fill_between",
            lambda self, *a, **k: fills.append(1),
        )
        monkeypatch.setattr(
            matplotlib.figure.Figure,
            "suptitle",
            lambda self, t, *a, **k: titles.append(t),
        )

        cfg = TimeCycleConfig(
            type="cycle",
            data=["grid_stub", "point_stub"],
            vars=["Temperatura"],
            time=TIME_INTERVAL,
            time_buckets="hour",
        )
        plot = TimeCycle(
            name="tc_band",
            plot_config=cfg,
            data_registry={
                "grid_stub": regular_grid_data,
                "point_stub": point_surface_data,
            },
            domain_registry={},
            output_path=tmp_output_dir,
        )
        plot.plot()

        # Two datasets are drawn, but only the reference (first) one has a std band.
        assert len(fills) == 1
        # Title must reference the configured bucket, not a hardcoded "Diurnal".
        assert titles and "Hour" in titles[0]


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
            time=TIME_INTERVAL,
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
            time=TIME_INTERVAL,
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
            time=TIME_INTERVAL,
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
            time=TIME_INTERVAL,
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
            data=["grid_stub", "point_stub"],
            time=TIME_INTERVAL,
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
