import pytest
from pydantic import ValidationError

from ClimateGraph.plot.plots import (
    ScatterConfig,
    SpatialMapConfig,
    SpatialOverlayConfig,
    TimeCycleConfig,
    TimeSeriesConfig,
)


class TestTimeSeriesConfig:
    def test_minimal(self):
        cfg = TimeSeriesConfig(type="timeseries", base="DMC", vars=["T"])
        assert cfg.base == "DMC"
        assert cfg.reduction_method.value == "mean"

    def test_alias_type_accepted(self):
        cfg = TimeSeriesConfig(type="ts", base="DMC", vars="T")
        assert cfg.type == "ts"

    def test_single_string_var_wrapped_in_list(self):
        # A lone string must become a one-element list, not be iterated char by
        # char downstream.
        cfg = TimeSeriesConfig(type="ts", base="DMC", vars="Temperatura")
        assert cfg.vars == ["Temperatura"]

    def test_list_and_dict_vars_untouched(self):
        assert TimeSeriesConfig(type="ts", base="DMC", vars=["A", "B"]).vars == [
            "A",
            "B",
        ]
        assert TimeSeriesConfig(type="ts", base="DMC", vars={"A": "kelvin"}).vars == {
            "A": "kelvin"
        }

    def test_unknown_type_rejected(self):
        with pytest.raises(ValidationError):
            TimeSeriesConfig(type="nope", base="DMC", vars="T")

    def test_invalid_timestep_rejected(self):
        with pytest.raises(ValidationError):
            TimeSeriesConfig(type="ts", base="DMC", vars="T", timestep="zzz")


class TestScatterConfig:
    def test_minimal(self):
        cfg = ScatterConfig(
            type="scatter",
            base="DMC",
            other="WRF",
            radius_of_influence=1000,
            time="1/1/2019 - 1/2/2019",
            vars={"T": "kelvin"},
        )
        assert cfg.dimension == "time"

    def test_radius_required(self):
        with pytest.raises(ValidationError):
            ScatterConfig(
                type="sc",
                base="A",
                other="B",
                time="1/1/2019 - 1/2/2019",
                vars="T",
            )


class TestSpatialOverlayConfig:
    def test_minimal(self):
        cfg = SpatialOverlayConfig(
            type="so",
            base="WRF",
            superposed="DMC",
            time="1/1/2019 - 1/2/2019",
            vars=["T"],
        )
        assert cfg.coastlines is True
        assert cfg.cmap == "viridis"
        assert cfg.padding == 0.05
        assert cfg.drop_nans is False


class TestSpatialMapConfig:
    def test_minimal(self):
        cfg = SpatialMapConfig(
            type="map",
            data="WRF",
            time="1/1/2019 - 1/2/2019",
            vars=["T"],
        )
        assert cfg.data == "WRF"
        assert cfg.coastlines is True
        assert cfg.cmap == "viridis"
        assert cfg.markersize == 40.0
        assert cfg.padding == 0.05
        assert cfg.drop_nans is False

    def test_data_required(self):
        with pytest.raises(ValidationError):
            SpatialMapConfig(
                type="sm",
                time="1/1/2019 - 1/2/2019",
                vars="T",
            )


class TestTimeCycleConfig:
    def test_minimal(self):
        cfg = TimeCycleConfig(
            type="timecycle",
            base="SINCA",
            vars=["PM10"],
        )
        assert cfg.time_buckets.value == "day"

    def test_timestep_finer_than_bucket_ok(self):
        cfg = TimeCycleConfig(
            type="cycle",
            base="X",
            vars="PM10",
            timestep="h",
            time_buckets="day",
        )
        assert cfg.timestep is not None

    def test_timestep_coarser_than_bucket_rejected(self):
        with pytest.raises(ValidationError, match="coarser"):
            TimeCycleConfig(
                type="cycle",
                base="X",
                vars="PM10",
                timestep="D",
                time_buckets="hour",
            )
