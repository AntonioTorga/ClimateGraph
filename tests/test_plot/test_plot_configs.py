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
        cfg = TimeSeriesConfig(type="timeseries", data="DMC", vars=["T"])
        assert cfg.data == ["DMC"]  # single dataset wrapped into a list
        assert cfg.reduction_method.value == "mean"

    def test_alias_type_accepted(self):
        cfg = TimeSeriesConfig(type="ts", data="DMC", vars="T")
        assert cfg.type == "ts"

    def test_multiple_datasets(self):
        cfg = TimeSeriesConfig(type="ts", data=["DMC", "WRF"], vars=["T"])
        assert cfg.data == ["DMC", "WRF"]

    def test_single_string_var_wrapped_in_list(self):
        # A lone string must become a one-element list, not be iterated char by
        # char downstream.
        cfg = TimeSeriesConfig(type="ts", data="DMC", vars="Temperatura")
        assert cfg.vars == ["Temperatura"]

    def test_list_and_dict_vars_untouched(self):
        assert TimeSeriesConfig(type="ts", data="DMC", vars=["A", "B"]).vars == [
            "A",
            "B",
        ]
        assert TimeSeriesConfig(type="ts", data="DMC", vars={"A": "kelvin"}).vars == {
            "A": "kelvin"
        }

    def test_unknown_type_rejected(self):
        with pytest.raises(ValidationError):
            TimeSeriesConfig(type="nope", data="DMC", vars="T")

    def test_invalid_timestep_rejected(self):
        with pytest.raises(ValidationError):
            TimeSeriesConfig(type="ts", data="DMC", vars="T", timestep="zzz")


class TestScatterConfig:
    def test_minimal(self):
        cfg = ScatterConfig(
            type="scatter",
            data=["DMC", "WRF"],
            time="1/1/2019 - 1/2/2019",
            vars={"T": "kelvin"},
        )
        assert cfg.dimension == "time"
        assert cfg.data == ["DMC", "WRF"]

    def test_exactly_two_datasets_required(self):
        with pytest.raises(ValidationError, match="exactly two"):
            ScatterConfig(
                type="sc",
                data=["A"],
                time="1/1/2019 - 1/2/2019",
                vars={"T": "kelvin"},
            )
        with pytest.raises(ValidationError, match="exactly two"):
            ScatterConfig(
                type="sc",
                data=["A", "B", "C"],
                time="1/1/2019 - 1/2/2019",
                vars={"T": "kelvin"},
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
            data="SINCA",
            vars=["PM10"],
        )
        assert cfg.data == ["SINCA"]
        assert cfg.time_buckets.value == "day"

    def test_timestep_finer_than_bucket_ok(self):
        cfg = TimeCycleConfig(
            type="cycle",
            data="X",
            vars="PM10",
            timestep="h",
            time_buckets="day",
        )
        assert cfg.timestep is not None

    def test_timestep_coarser_than_bucket_rejected(self):
        with pytest.raises(ValidationError, match="coarser"):
            TimeCycleConfig(
                type="cycle",
                data="X",
                vars="PM10",
                timestep="D",
                time_buckets="hour",
            )
