import datetime
import logging

import numpy as np
import pytest

from ClimateGraph.utils.general_utils import (
    CRSEnum,
    ReductionMethodEnum,
    TimestepEnum,
    TimeBucketEnum,
    manage_path,
    manage_time_interval,
)


class TestManageTimeInterval:
    def test_dash_separator_dayfirst(self):
        start, end = manage_time_interval("1/2/2019 - 31/3/2019")
        assert start == datetime.datetime(2019, 2, 1)
        assert end == datetime.datetime(2019, 3, 31)

    def test_to_separator(self):
        start, end = manage_time_interval("1/1/2020 to 1/2/2020")
        assert start.month == 1 and end.month == 2

    def test_no_separator_raises(self):
        with pytest.raises(ValueError):
            manage_time_interval("just a single date")

    def test_invalid_date_raises(self):
        with pytest.raises(Exception):
            manage_time_interval("not-a-date - also-not")


class TestManagePath:
    def test_single_string_path(self, tmp_path):
        target = tmp_path / "a.nc"
        target.write_bytes(b"")
        result = manage_path(str(target))
        assert result == [target.resolve()]

    def test_glob_expansion(self, tmp_path):
        for name in ("a.nc", "b.nc"):
            (tmp_path / name).write_bytes(b"")
        result = manage_path(str(tmp_path / "*.nc"))
        assert {p.name for p in result} == {"a.nc", "b.nc"}

    def test_list_of_paths(self, tmp_path):
        files = [tmp_path / n for n in ("x.nc", "y.nc")]
        for f in files:
            f.write_bytes(b"")
        result = manage_path([str(f) for f in files])
        assert len(result) == 2

    def test_missing_path_returns_empty(self, tmp_path, caplog):
        with caplog.at_level(logging.DEBUG):
            result = manage_path(str(tmp_path / "does-not-exist.nc"))
        assert result == []


class TestEnums:
    def test_timestep_enum_values(self):
        assert TimestepEnum.daily.value == "D"
        assert TimestepEnum.hourly.value == "h"

    def test_reduction_method_callable_attached(self):
        arr = np.array([1.0, 2.0, np.nan, 4.0])
        assert ReductionMethodEnum.mean.func(arr) == pytest.approx(7 / 3)
        assert ReductionMethodEnum.min.func(arr) == 1.0
        assert ReductionMethodEnum.max.func(arr) == 4.0

    def test_reduction_method_value_string(self):
        # The Pydantic-facing string value must match what's used in YAML.
        assert ReductionMethodEnum.mean.value == "mean"

    def test_crs_enum_has_crs_attribute(self):
        import cartopy.crs as ccrs

        assert CRSEnum.platecarree.crs is ccrs.PlateCarree

    def test_time_bucket_enum_keys(self):
        # These keys back the groupby in TimeCycle; protect them.
        assert TimeBucketEnum.day.value == "day"
        assert TimeBucketEnum.hour.value == "hour"
