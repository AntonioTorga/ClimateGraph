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
