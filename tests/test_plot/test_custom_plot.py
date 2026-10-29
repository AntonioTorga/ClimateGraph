"""Custom (type: custom) plot — var-scope config rules and end-to-end runs."""

from __future__ import annotations

import matplotlib as mpl
import numpy as np
import pytest
import xarray as xr
from pydantic import ValidationError

mpl.use("Agg")

from ClimateGraph.plot import Plot
from ClimateGraph.plot.plots import Custom, CustomPlotConfig
from ClimateGraph.utils.control_model import PlotModel  # noqa: F401 (union built)

TIME_INTERVAL = "1/1/2019 - 6/1/2019"


def _outputs(out_dir, name):
    return list((out_dir / name).iterdir())


class TestCustomConfigVarScope:
    def test_custom_registered(self):
        assert Plot.get_plot_class("custom") is Custom

    def test_plot_vars_only_ok(self):
        cfg = CustomPlotConfig(
            type="custom",
            vars=["Temperatura"],
            subplots=[{"type": "contourf", "dataset": "g", "x": "lon", "y": "lat"}],
        )
        assert cfg.vars == ["Temperatura"]

    def test_subplot_vars_only_ok(self):
        cfg = CustomPlotConfig(
            type="custom",
            subplots=[
                {"type": "series", "dataset": "g", "x": "time", "var": "CO"},
                {"type": "series", "dataset": "o", "x": "time", "var": "NO2"},
            ],
        )
        assert cfg.vars is None

    def test_both_scopes_rejected(self):
        with pytest.raises(ValidationError):
            CustomPlotConfig(
                type="custom",
                vars=["Temperatura"],
                subplots=[{"type": "series", "dataset": "g", "x": "time", "var": "CO"}],
            )

    def test_partial_subplot_vars_rejected(self):
        # Some subplots with var, some without, and no plot-level vars → ambiguous.
        with pytest.raises(ValidationError):
            CustomPlotConfig(
                type="custom",
                subplots=[
                    {"type": "series", "dataset": "g", "x": "time", "var": "CO"},
                    {"type": "series", "dataset": "o", "x": "time"},
                ],
            )

    def test_empty_subplots_rejected(self):
        with pytest.raises(ValidationError):
            CustomPlotConfig(type="custom", vars=["T"], subplots=[])


class TestCustomProjectionRules:
    ROSE = {"type": "rose", "dataset": "s", "angle": "WD", "radius": "WS"}

    def test_rose_accepted_on_polar(self):
        cfg = CustomPlotConfig(
            type="custom", projection="polar", vars=["PM25"], subplots=[self.ROSE]
        )
        assert cfg.projection.mpl == "polar"

    def test_rose_rejected_on_rectilinear(self):
        with pytest.raises(ValidationError, match="projection: polar"):
            CustomPlotConfig(type="custom", vars=["PM25"], subplots=[self.ROSE])

    def test_other_primitives_accept_any_projection(self):
        series = {"type": "series", "dataset": "s", "x": "time"}
        CustomPlotConfig(type="custom", vars=["PM25"], subplots=[series])
        CustomPlotConfig(
            type="custom", projection="polar", vars=["PM25"], subplots=[series]
        )

    def test_angular_rejected_without_polar(self):
        with pytest.raises(ValidationError, match="projection: polar"):
            CustomPlotConfig(
                type="custom",
                angular={"period": 360},
                vars=["PM25"],
                subplots=[{"type": "series", "dataset": "s", "x": "time"}],
            )


class TestResolveKeepDims:
    def test_two_d_coordinate_resolves_to_underlying_dims(self):
        # The crux of the x/y design: naming 2-D coordinates longitude/latitude
        # (over dims y,x) must keep {y, x}, not literal {longitude, latitude}.
        lat2, lon2 = np.meshgrid(
            np.linspace(-36, -33, 4), np.linspace(-73, -69, 5), indexing="ij"
        )
        da = xr.DataArray(
            np.zeros((4, 5)),
            dims=("y", "x"),
            coords={
                "latitude": (("y", "x"), lat2),
                "longitude": (("y", "x"), lon2),
            },
        )
        keep = Custom._resolve_keep_dims(da, "longitude", "latitude")
        assert keep == {"y", "x"}

    def test_literal_dim_fallback(self):
        da = xr.DataArray(np.zeros(6), dims=("time",), coords={"time": range(6)})
        assert Custom._resolve_keep_dims(da, "time", None) == {"time"}


class TestRoseRuns:
    INTERVAL = "1/1/2019 - 6/1/2019"

    def _config(self, **subplot):
        return CustomPlotConfig(
            type="custom",
            projection="polar",
            angular={"period": 360},
            vars={"PM25": "ug/m**3"},
            time=self.INTERVAL,
            subplots=[
                {"type": "rose", "dataset": "wind", "angle": "WD", "radius": "WS"}
                | subplot
            ],
        )

    def _run(self, cfg, data, out, monkeypatch):
        """Draw, and hand back the figure on its way to disk."""
        plot = Custom(
            name="rose",
            plot_config=cfg,
            data_registry={"wind": data},
            domain_registry={},
            output_path=out,
        )
        captured = {}
        write = plot.savefig

        def spy(figure, filename):
            captured["figure"] = figure
            write(figure, filename)

        monkeypatch.setattr(plot, "savefig", spy)
        plot.plot()
        return captured["figure"]

    def test_rose_renders(self, wind_station_data, tmp_output_dir, monkeypatch):
        self._run(self._config(), wind_station_data, tmp_output_dir, monkeypatch)
        assert len(_outputs(tmp_output_dir, "rose")) == 1

    def test_rose_draws_a_legend_and_no_colorbar(
        self, wind_station_data, tmp_output_dir, monkeypatch
    ):
        figure = self._run(
            self._config(), wind_station_data, tmp_output_dir, monkeypatch
        )
        assert [a.get_label() for a in figure.axes] == [""]
        legends = [
            a for a in figure.axes[0].artists if isinstance(a, mpl.legend.Legend)
        ]
        assert legends and legends[0].get_title().get_text() == "PM25 [ug/m**3]"

    def test_rose_labels_the_radial_axis_with_its_radius(
        self, wind_station_data, tmp_output_dir, monkeypatch
    ):
        # Not the plot variable, which is the colour rather than the radius.
        figure = self._run(
            self._config(), wind_station_data, tmp_output_dir, monkeypatch
        )
        assert figure.axes[0].get_ylabel() == "WS"

    def test_explicit_radius_edges_render(
        self, wind_station_data, tmp_output_dir, monkeypatch
    ):
        cfg = self._config(radius_bins=[0, 2, 4, 8])
        self._run(cfg, wind_station_data, tmp_output_dir, monkeypatch)
        assert len(_outputs(tmp_output_dir, "rose")) == 1

    def test_count_rose_renders_without_a_variable(
        self, wind_station_data, tmp_output_dir, monkeypatch
    ):
        cfg = CustomPlotConfig(
            type="custom",
            projection="polar",
            time=self.INTERVAL,
            subplots=[
                {"type": "rose", "dataset": "wind", "angle": "WD", "radius": "WS"}
            ],
        )
        figure = self._run(cfg, wind_station_data, tmp_output_dir, monkeypatch)
        legends = [
            a for a in figure.axes[0].artists if isinstance(a, mpl.legend.Legend)
        ]
        assert legends[0].get_title().get_text() == "samples"


class TestCustomRuns:
    def _make(self, cfg, registry, out):
        return Custom(
            name="combo",
            plot_config=cfg,
            data_registry=registry,
            domain_registry={},
            output_path=out,
        )

    def test_contourf_plus_points_shared_axes(
        self, regular_grid_data, point_surface_data, tmp_output_dir
    ):
        cfg = CustomPlotConfig(
            type="custom",
            vars=["Temperatura"],
            time=TIME_INTERVAL,
            subplots=[
                {
                    "type": "contourf",
                    "dataset": "grid",
                    "x": "longitude",
                    "y": "latitude",
                },
                {
                    "type": "points",
                    "dataset": "pts",
                    "x": "longitude",
                    "y": "latitude",
                },
            ],
        )
        self._make(
            cfg, {"grid": regular_grid_data, "pts": point_surface_data}, tmp_output_dir
        ).plot()
        outs = _outputs(tmp_output_dir, "combo")
        assert len(outs) == 1
        assert "custom--Temperatura-01-01-2019_06-01-2019" in outs[0].name

    def test_raster_on_curvilinear_coords(self, regular_grid_data, tmp_output_dir):
        # RegularGrid carries 2-D latitude/longitude; this is the case imshow
        # cannot draw at all ("imshow requires 1D coordinates").
        cfg = CustomPlotConfig(
            type="custom",
            vars=["Temperatura"],
            time=TIME_INTERVAL,
            subplots=[
                {
                    "type": "raster",
                    "dataset": "grid",
                    "x": "longitude",
                    "y": "latitude",
                }
            ],
        )
        self._make(cfg, {"grid": regular_grid_data}, tmp_output_dir).plot()
        assert len(_outputs(tmp_output_dir, "combo")) == 1

    def test_raster_under_contour_lines(self, regular_grid_data, tmp_output_dir):
        # The pairing the single-colour decision is for: the mesh owns the
        # colour scale, the lines carry their values on inline labels.
        cfg = CustomPlotConfig(
            type="custom",
            vars=["Temperatura"],
            time=TIME_INTERVAL,
            subplots=[
                {
                    "type": "raster",
                    "dataset": "grid",
                    "x": "longitude",
                    "y": "latitude",
                },
                {
                    "type": "contour",
                    "dataset": "grid",
                    "x": "longitude",
                    "y": "latitude",
                    "levels": 5,
                },
            ],
        )
        self._make(cfg, {"grid": regular_grid_data}, tmp_output_dir).plot()
        assert len(_outputs(tmp_output_dir, "combo")) == 1

    def test_series_along_time(self, point_surface_data, tmp_output_dir):
        cfg = CustomPlotConfig(
            type="custom",
            vars=["Temperatura"],
            time=TIME_INTERVAL,
            subplots=[{"type": "series", "dataset": "pts", "x": "time"}],
        )
        self._make(cfg, {"pts": point_surface_data}, tmp_output_dir).plot()
        assert _outputs(tmp_output_dir, "combo")

    def test_cross_variable_composition_filename_token(
        self, regular_grid_data, tmp_output_dir
    ):
        # Subplot-scoped vars (different vars, same figure) → "A+B" filename token.
        cfg = CustomPlotConfig(
            type="custom",
            time=TIME_INTERVAL,
            subplots=[
                {
                    "type": "contourf",
                    "dataset": "grid",
                    "x": "longitude",
                    "y": "latitude",
                    "var": "Temperatura",
                },
                {
                    "type": "points",
                    "dataset": "grid",
                    "x": "longitude",
                    "y": "latitude",
                    "var": "Presion",
                },
            ],
        )
        self._make(cfg, {"grid": regular_grid_data}, tmp_output_dir).plot()
        outs = _outputs(tmp_output_dir, "combo")
        assert len(outs) == 1
        assert "Temperatura+Presion" in outs[0].name

    def test_unit_precedence_subplot_wins(self, regular_grid_data, tmp_output_dir):
        # subplot.unit overrides a plot-level vars-dict unit.
        cfg = CustomPlotConfig(
            type="custom",
            vars={"Temperatura": "degC"},
            time=TIME_INTERVAL,
            subplots=[
                {
                    "type": "contourf",
                    "dataset": "grid",
                    "x": "longitude",
                    "y": "latitude",
                    "unit": "kelvin",
                }
            ],
        )
        plot = self._make(cfg, {"grid": regular_grid_data}, tmp_output_dir)
        _, dst_unit = plot._prepare_subplot_data(
            cfg.subplots[0], None, "Temperatura", TIME_INTERVAL
        )
        assert dst_unit == "kelvin"

    def test_subplot_time_override_renders(self, point_surface_data, tmp_output_dir):
        # No plot-level time (single figure); the subplot pins its own window.
        cfg = CustomPlotConfig(
            type="custom",
            vars=["Temperatura"],
            subplots=[
                {
                    "type": "series",
                    "dataset": "pts",
                    "x": "time",
                    "time": "1/1/2019 - 3/1/2019",
                }
            ],
        )
        self._make(cfg, {"pts": point_surface_data}, tmp_output_dir).plot()
        assert _outputs(tmp_output_dir, "combo")

    def test_two_times_overlay_on_one_figure(self, point_surface_data, tmp_output_dir):
        # The "same var, two windows" comparison: subplot-scoped vars, each with
        # its own time, must land on ONE figure (no plot-level time fan-out).
        cfg = CustomPlotConfig(
            type="custom",
            subplots=[
                {
                    "type": "series",
                    "dataset": "pts",
                    "x": "time",
                    "var": "Temperatura",
                    "time": "1/1/2019 - 3/1/2019",
                    "label": "early",
                },
                {
                    "type": "series",
                    "dataset": "pts",
                    "x": "time",
                    "var": "Temperatura",
                    "time": "4/1/2019 - 6/1/2019",
                    "label": "late",
                },
            ],
        )
        self._make(cfg, {"pts": point_surface_data}, tmp_output_dir).plot()
        assert len(_outputs(tmp_output_dir, "combo")) == 1

    def test_unit_falls_back_to_plot_vars_dict(self, regular_grid_data, tmp_output_dir):
        cfg = CustomPlotConfig(
            type="custom",
            vars={"Temperatura": "degC"},
            time=TIME_INTERVAL,
            subplots=[
                {
                    "type": "contourf",
                    "dataset": "grid",
                    "x": "longitude",
                    "y": "latitude",
                }
            ],
        )
        plot = self._make(cfg, {"grid": regular_grid_data}, tmp_output_dir)
        _, dst_unit = plot._prepare_subplot_data(
            cfg.subplots[0], None, "Temperatura", TIME_INTERVAL
        )
        assert dst_unit == "degC"
