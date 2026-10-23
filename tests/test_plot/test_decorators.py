"""Decorations (the ``decorations:`` block) — resolution, config rules, runs."""

from __future__ import annotations

import matplotlib as mpl
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from pydantic import ValidationError

mpl.use("Agg")

from ClimateGraph.plot.decorator import Decorator
from ClimateGraph.plot.decorators import (
    HLine,
    HLineConfig,
    VLine,
    VLineConfig,
    _reference_value,
)
from ClimateGraph.plot.plots import Custom, CustomPlotConfig
from ClimateGraph.utils.general_utils import ReferenceEnum, expand

TIME_INTERVAL = "1/1/2019 - 6/1/2019"


def _outputs(out_dir, name):
    return list((out_dir / name).iterdir())


@pytest.fixture
def series():
    """A 1-D array over time with a known shape: min 0.0, max 9.0, mean 4.5."""
    return xr.DataArray(
        np.arange(10, dtype=float),
        dims="time",
        coords={"time": pd.date_range("2019-01-01", periods=10, freq="D")},
    )


class TestDecoratorRegistry:
    def test_canonical_names_registered(self):
        assert Decorator.get_decorator_class("hline") is HLine
        assert Decorator.get_decorator_class("vline") is VLine

    def test_aliases_registered(self):
        assert Decorator.get_decorator_class("threshold") is HLine
        assert Decorator.get_decorator_class("marker") is VLine

    def test_shared_abstract_base_is_not_addressable(self):
        # The Line base carries styling only; naming it in a control file could
        # never work, so the registry must not offer it.
        assert Decorator.check_decorator_class("line") is False


class TestReferenceValue:
    def test_literal_number_passes_through(self):
        assert _reference_value(None, 50.0) == 50.0

    @pytest.mark.parametrize(
        ("statistic", "expected"),
        [("mean", 4.5), ("median", 4.5), ("min", 0.0), ("max", 9.0), ("p90", 8.1)],
    )
    def test_statistics(self, series, statistic, expected):
        got = _reference_value(series, ReferenceEnum(statistic))
        assert got == pytest.approx(expected)

    def test_statistics_ignore_nans(self):
        data = xr.DataArray(np.array([1.0, np.nan, 3.0]), dims="time")
        assert _reference_value(data, ReferenceEnum.mean) == pytest.approx(2.0)

    def test_argmax_returns_the_coordinate_not_the_value(self, series):
        # The point of argmax for a vline: *where* the peak is, not how big.
        got = _reference_value(series, ReferenceEnum.argmax, coord="time")
        assert got == np.datetime64("2019-01-10")

    def test_argmin_returns_the_coordinate(self, series):
        got = _reference_value(series, ReferenceEnum.argmin, coord="time")
        assert got == np.datetime64("2019-01-01")

    def test_date_string_is_read_dayfirst(self):
        got = _reference_value(None, "6/1/2019")
        assert (got.day, got.month) == (6, 1)

    def test_statistic_without_data_is_rejected(self):
        with pytest.raises(ValueError, match="no dataset was given"):
            _reference_value(None, ReferenceEnum.mean)

    def test_argmax_without_coord_is_rejected(self, series):
        with pytest.raises(ValueError, match="needs 'x'"):
            _reference_value(series, ReferenceEnum.argmax)

    def test_argmax_with_mismatched_coord_is_rejected(self):
        data = xr.DataArray(
            np.arange(6.0).reshape(3, 2),
            dims=("time", "site"),
            coords={"time": pd.date_range("2019-01-01", periods=3)},
        )
        with pytest.raises(ValueError, match="one-to-one"):
            _reference_value(data, ReferenceEnum.argmax, coord="time")

    def test_bool_is_not_a_position(self, series):
        with pytest.raises(TypeError):
            _reference_value(series, True)


class TestLineConfigs:
    def test_named_statistic_beats_the_date_branch(self):
        # "mean" is a plain str too; the smart union would otherwise take it as
        # a date and never reach the enum.
        cfg = HLineConfig(type="hline", dataset="d", at="mean")
        assert cfg.at is ReferenceEnum.mean

    def test_number_stays_a_number(self):
        assert HLineConfig(type="hline", at=50).at == 50.0

    def test_unrecognised_string_is_kept_as_a_date(self):
        assert VLineConfig(type="vline", at="15/6/2021").at == "15/6/2021"

    def test_statistic_requires_a_dataset(self):
        with pytest.raises(ValidationError, match="statistics of the data"):
            HLineConfig(type="hline", at="p95")

    def test_literal_needs_no_dataset(self):
        assert HLineConfig(type="hline", at=50).dataset is None

    def test_argextreme_requires_x(self):
        with pytest.raises(ValidationError, match="argmax/argmin"):
            VLineConfig(type="vline", dataset="d", at="argmax")

    def test_styling_flows_through_model_extra(self):
        cfg = HLineConfig(type="hline", at=50, color="red", linestyle=":")
        assert cfg.model_extra == {"color": "red", "linestyle": ":"}
        assert HLine("p", cfg).style == {"color": "red", "linestyle": ":"}

    def test_only_labelled_lines_want_a_legend(self):
        assert HLine("p", HLineConfig(type="hline", at=50)).wants_legend is False
        labelled = HLineConfig(type="hline", at=50, label="Norma")
        assert HLine("p", labelled).wants_legend is True


class TestLineExpansion:
    def test_list_of_positions_fans_out(self):
        cfg = HLineConfig(type="hline", dataset="d", at=[50, "mean", "p95"])
        positions = [one.at for _, one in expand(cfg)]
        assert positions == [50.0, ReferenceEnum.mean, ReferenceEnum.p95]

    def test_single_position_yields_one(self):
        assert len(expand(HLineConfig(type="hline", at=50))) == 1

    def test_slot_token_is_the_statistic_name(self):
        # Feeds `label: "Obs {at}"`; a bare enum would format as
        # "ReferenceEnum.mean".
        slots, _ = expand(HLineConfig(type="hline", dataset="d", at=["mean"]))[0]
        assert slots["at"] == "mean"

    def test_styling_is_shared_by_every_expansion(self):
        cfg = HLineConfig(type="hline", dataset="d", at=["mean", "max"], color="red")
        assert all(one.model_extra["color"] == "red" for _, one in expand(cfg))


class TestDecorationVarScope:
    def test_dataset_without_var_needs_plot_vars(self):
        with pytest.raises(ValidationError, match="no 'var'"):
            CustomPlotConfig(
                type="custom",
                subplots=[
                    {"type": "series", "dataset": "g", "x": "time", "var": "CO"}
                ],
                decorations=[{"type": "hline", "dataset": "g", "at": "mean"}],
            )

    def test_literal_decoration_needs_nothing(self):
        cfg = CustomPlotConfig(
            type="custom",
            subplots=[{"type": "series", "dataset": "g", "x": "time", "var": "CO"}],
            decorations=[{"type": "hline", "at": 50}],
        )
        assert len(cfg.decorations) == 1


class TestDecorationRuns:
    def _make(self, cfg, registry, out):
        return Custom(
            name="combo",
            plot_config=cfg,
            data_registry=registry,
            domain_registry={},
            output_path=out,
        )

    def _config(self, decorations):
        return CustomPlotConfig(
            type="custom",
            vars=["Temperatura"],
            time=TIME_INTERVAL,
            subplots=[{"type": "series", "dataset": "pts", "x": "time"}],
            decorations=decorations,
        )

    def test_literal_and_derived_lines_render(
        self, point_surface_data, tmp_output_dir
    ):
        cfg = self._config(
            [
                {"type": "hline", "at": 50, "label": "Norma", "color": "red"},
                {"type": "hline", "dataset": "pts", "at": "p95", "label": "P95"},
            ]
        )
        self._make(cfg, {"pts": point_surface_data}, tmp_output_dir).plot()
        assert len(_outputs(tmp_output_dir, "combo")) == 1

    def test_vline_at_argmax_renders(self, point_surface_data, tmp_output_dir):
        # A decoration is handed its data unreduced, which is what makes p95
        # meaningful. argmax needs a series, so the other dims are named here.
        cfg = self._config(
            [
                {
                    "type": "vline",
                    "dataset": "pts",
                    "x": "time",
                    "at": "argmax",
                    "dim_reduce": {"site": "mean"},
                }
            ]
        )
        self._make(cfg, {"pts": point_surface_data}, tmp_output_dir).plot()
        assert len(_outputs(tmp_output_dir, "combo")) == 1

    def test_argmax_over_extra_dims_says_how_to_fix_it(
        self, point_surface_data, tmp_output_dir
    ):
        cfg = self._config(
            [{"type": "vline", "dataset": "pts", "x": "time", "at": "argmax"}]
        )
        plot = self._make(cfg, {"pts": point_surface_data}, tmp_output_dir)
        with pytest.raises(ValueError, match="dim_reduce"):
            plot.plot()

    def test_decorations_draw_after_every_primitive(
        self, point_surface_data, tmp_output_dir, monkeypatch
    ):
        # The whole point of a second pass: an annotation lands on top, over
        # axes whose limits the primitives have already settled.
        from ClimateGraph.plot.primitives import Series

        order = []
        primitive_render, decorator_draw = Series.render, HLine.draw

        def spy_render(self, *a, **kw):
            order.append("primitive")
            return primitive_render(self, *a, **kw)

        def spy_draw(self, *a, **kw):
            order.append("decoration")
            return decorator_draw(self, *a, **kw)

        monkeypatch.setattr(Series, "render", spy_render)
        monkeypatch.setattr(HLine, "draw", spy_draw)

        cfg = self._config([{"type": "hline", "at": 50}])
        self._make(cfg, {"pts": point_surface_data}, tmp_output_dir).plot()
        assert order == ["primitive", "decoration"]

    def test_expanded_positions_each_draw(
        self, point_surface_data, tmp_output_dir, monkeypatch
    ):
        drawn = []
        original = HLine.draw

        def spy(self, ax, data):
            drawn.append(self.decoration_config.at)
            return original(self, ax, data)

        monkeypatch.setattr(HLine, "draw", spy)
        cfg = self._config(
            [{"type": "hline", "dataset": "pts", "at": [0, "mean", "max"]}]
        )
        self._make(cfg, {"pts": point_surface_data}, tmp_output_dir).plot()
        assert drawn == [0.0, ReferenceEnum.mean, ReferenceEnum.max]

    def test_label_template_names_each_expansion(
        self, point_surface_data, tmp_output_dir, monkeypatch
    ):
        labels = []
        original = HLine.draw

        def spy(self, ax, data):
            labels.append(self.decoration_config.label)
            return original(self, ax, data)

        monkeypatch.setattr(HLine, "draw", spy)
        cfg = self._config(
            [
                {
                    "type": "hline",
                    "dataset": "pts",
                    "at": ["mean", "p95"],
                    "label": "Obs {at}",
                }
            ]
        )
        self._make(cfg, {"pts": point_surface_data}, tmp_output_dir).plot()
        assert labels == ["Obs mean", "Obs p95"]

    def test_plain_label_survives_expansion(
        self, point_surface_data, tmp_output_dir, monkeypatch
    ):
        # No placeholder: the label is used as written, not treated as a format
        # string that silently loses braces.
        labels = []
        original = HLine.draw

        def spy(self, ax, data):
            labels.append(self.decoration_config.label)
            return original(self, ax, data)

        monkeypatch.setattr(HLine, "draw", spy)
        cfg = self._config([{"type": "hline", "at": 50, "label": "Norma diaria"}])
        self._make(cfg, {"pts": point_surface_data}, tmp_output_dir).plot()
        assert labels == ["Norma diaria"]
