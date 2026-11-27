"""Custom (type: custom) plot — var-scope config rules and end-to-end runs."""

from __future__ import annotations

import logging
from pathlib import Path

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


def _stub_grid(dataset, name):
    """A RegularGrid wearing an in-memory dataset, like the conftest fixture."""
    import cartopy.crs as ccrs

    from ClimateGraph.data import RegularGrid

    instance = RegularGrid(
        name=name,
        path=Path(f"memory://{name}"),
        vars={"Temperatura": {"name": "Temperatura", "unit": "kelvin"}},
        reader=type("_StubReader", (), {"read": staticmethod(lambda spec: dataset)}),
        crs=ccrs.PlateCarree(),
    )
    instance.obj = dataset
    return instance


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

    def test_a_subplot_var_overrides_the_plot_level_vars(self):
        # Pins one layer while the plot fans out over several variables.
        cfg = CustomPlotConfig(
            type="custom",
            vars=["Temperatura", "Presion"],
            subplots=[
                {"type": "series", "dataset": "g", "x": "time", "var": "CO"},
                {"type": "series", "dataset": "g", "x": "time"},
            ],
        )
        assert cfg.subplots[0].var == "CO"
        assert cfg.subplots[1].var is None

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


class TestExpectedFigures:
    def test_matches_what_is_written(self, regular_grid_data, tmp_output_dir):
        # The run summary promises this number before opening a file.
        cfg = CustomPlotConfig(
            type="custom",
            vars=["Temperatura", "Presion"],
            time=["1/1/2019 - 3/1/2019", "4/1/2019 - 6/1/2019"],
            subplots=[{"type": "series", "dataset": "grid", "x": "time"}],
        )
        plot = Custom(
            name="counted",
            plot_config=cfg,
            data_registry={"grid": regular_grid_data},
            domain_registry={},
            output_path=tmp_output_dir,
        )
        promised = plot.expected_figures()
        plot.plot()
        assert promised == 4
        assert len(_outputs(tmp_output_dir, "counted")) == promised

    def test_a_plot_with_no_fan_out_is_one_figure(self, regular_grid_data):
        cfg = CustomPlotConfig(
            type="custom",
            vars=["Temperatura"],
            subplots=[{"type": "series", "dataset": "grid", "x": "time"}],
        )
        plot = Custom(
            name="single",
            plot_config=cfg,
            data_registry={"grid": regular_grid_data},
            domain_registry={},
            output_path=Path("."),
        )
        assert plot.expected_figures() == 1


class TestNameTemplateValidation:
    """A bad template is a config error, not a traceback mid-run."""

    def _cfg(self, **overrides):
        return CustomPlotConfig(
            type="custom",
            vars=["T"],
            subplots=[{"type": "series", "dataset": "d", "x": "time"}],
            **overrides,
        )

    def test_known_tokens_accepted(self):
        cfg = self._cfg(filename="{var}/{domain}-{time}", title="{var} in {domain}")
        assert cfg.filename == "{var}/{domain}-{time}"

    def test_a_plain_name_is_not_a_template(self):
        assert self._cfg(filename="mychart").filename == "mychart"

    @pytest.mark.parametrize("field", ["filename", "title"])
    def test_an_unknown_token_is_rejected(self, field):
        with pytest.raises(ValidationError, match="unknown token"):
            self._cfg(**{field: "{timestep}"})

    def test_the_error_names_the_vocabulary(self):
        with pytest.raises(ValidationError, match=r"domain.*time.*var"):
            self._cfg(filename="{nope}")

    def test_a_positional_field_is_rejected(self):
        # "{0}" parses as a name, and no figure supplies one.
        with pytest.raises(ValidationError, match="unknown token"):
            self._cfg(filename="{0}")

    def test_malformed_braces_are_rejected(self):
        with pytest.raises(ValidationError, match="not a usable template"):
            self._cfg(filename="{var")


class TestCustomNaming:
    """An explicit ``filename:`` used to write N figures to one path."""

    def _plot(self, data, out, **overrides):
        # title/format are extras, which the config carries and the plot reads
        # back through plot_kwargs.
        cfg = CustomPlotConfig(
            type="custom",
            vars=["Temperatura"],
            subplots=[{"type": "series", "dataset": "grid", "x": "time"}],
            format="png",
            **overrides,
        )
        Custom(
            name="named",
            plot_config=cfg,
            data_registry={"grid": data},
            domain_registry={},
            output_path=out,
        ).plot()
        return sorted(p.name for p in _outputs(out, "named"))

    def test_a_fan_out_writes_one_file_per_figure(
        self, regular_grid_data, tmp_output_dir
    ):
        names = self._plot(
            regular_grid_data,
            tmp_output_dir,
            filename="mychart",
            time=["1/1/2019 - 3/1/2019", "4/1/2019 - 6/1/2019"],
        )
        assert len(names) == 2
        assert names == [
            "mychart-01-01-2019_03-01-2019.png",
            "mychart-04-01-2019_06-01-2019.png",
        ]

    def test_without_a_fan_out_the_name_is_exactly_what_was_written(
        self, regular_grid_data, tmp_output_dir
    ):
        names = self._plot(
            regular_grid_data, tmp_output_dir, filename="mychart", time="1/1/2019"
        )
        assert names == ["mychart.png"]

    def test_a_template_may_name_subdirectories(
        self, regular_grid_data, tmp_output_dir
    ):
        self._plot(
            regular_grid_data,
            tmp_output_dir,
            filename="{var}/{time}",
            time="1/1/2019",
        )
        written = list((tmp_output_dir / "named").rglob("*.png"))
        assert [
            p.relative_to(tmp_output_dir / "named").as_posix() for p in written
        ] == ["Temperatura/01-01-2019.png"]

    def test_the_title_reads_the_same_tokens(
        self, regular_grid_data, tmp_output_dir, monkeypatch
    ):
        captured = {}
        original = mpl.figure.Figure.suptitle

        def spy(figure, text, *args, **kwargs):
            captured["title"] = text
            return original(figure, text, *args, **kwargs)

        monkeypatch.setattr(mpl.figure.Figure, "suptitle", spy)
        self._plot(
            regular_grid_data,
            tmp_output_dir,
            time="1/1/2019",
            title="{var} on {time}",
        )
        assert captured["title"] == "Temperatura on 01-01-2019"


class TestBandRuns:
    def _run(self, data, out, projection="rectilinear", **subplot):
        cfg = CustomPlotConfig(
            type="custom",
            projection=projection,
            angular={"cycle": "hour"} if projection == "polar" else None,
            vars=["Temperatura"],
            time=TIME_INTERVAL,
            subplots=[{"type": "band", "dataset": "grid", "x": "time"} | subplot],
        )
        Custom(
            name="band",
            plot_config=cfg,
            data_registry={"grid": data},
            domain_registry={},
            output_path=out,
        ).plot()
        return _outputs(out, "band")

    def test_spread_renders(self, regular_grid_data, tmp_output_dir):
        assert len(self._run(regular_grid_data, tmp_output_dir, spread="std")) == 1

    def test_minmax_renders(self, regular_grid_data, tmp_output_dir):
        assert len(self._run(regular_grid_data, tmp_output_dir, spread="minmax")) == 1

    def test_explicit_edges_render(self, regular_grid_data, tmp_output_dir):
        outputs = self._run(
            regular_grid_data,
            tmp_output_dir,
            lower="Temperatura",
            upper="Presion",
        )
        assert len(outputs) == 1

    def test_edges_from_two_datasets_render(
        self, regular_grid_data, point_surface_data, tmp_output_dir
    ):
        # The case a single `dataset:` cannot express.
        cfg = CustomPlotConfig(
            type="custom",
            time=TIME_INTERVAL,
            subplots=[
                {
                    "type": "band",
                    "x": "time",
                    "lower": "pts::Temperatura",
                    "upper": "grid::Temperatura",
                }
            ],
        )
        Custom(
            name="band",
            plot_config=cfg,
            data_registry={"grid": regular_grid_data, "pts": point_surface_data},
            domain_registry={},
            output_path=tmp_output_dir,
        ).plot()
        assert len(_outputs(tmp_output_dir, "band")) == 1

    def test_mismatched_axes_intersect_rather_than_widen(
        self, make_regular_grid, tmp_output_dir, caplog
    ):
        """Building a Dataset would outer-join: the axis widens and the gaps
        fill with NaN, silently. An inner join covers only where both have
        data, and says so."""
        early = _stub_grid(make_regular_grid(n_time=6, start="2019-01-01"), "early")
        late = _stub_grid(make_regular_grid(n_time=6, start="2019-01-04"), "late")
        cfg = CustomPlotConfig(
            type="custom",
            subplots=[
                {
                    "type": "band",
                    "x": "time",
                    "lower": "early::Temperatura",
                    "upper": "late::Temperatura",
                }
            ],
        )
        plot = Custom(
            name="band",
            plot_config=cfg,
            data_registry={"early": early, "late": late},
            domain_registry={},
            output_path=tmp_output_dir,
        )
        with caplog.at_level(logging.WARNING, logger="ClimateGraph.plot.plots"):
            prepared, _ = plot._prepare_subplot_data(cfg.subplots[0], None, None, None)
        # 6 days each, overlapping on 3.
        assert prepared.sizes["time"] == 3
        assert not prepared["lower"].isnull().any()
        assert not prepared["upper"].isnull().any()
        assert "lost" in caplog.text

    def test_renders_on_polar_axes(self, regular_grid_data, tmp_output_dir):
        outputs = self._run(
            regular_grid_data, tmp_output_dir, projection="polar", spread="std"
        )
        assert len(outputs) == 1


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
