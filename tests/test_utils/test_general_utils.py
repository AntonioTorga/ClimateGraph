import logging

import numpy as np
import pandas as pd
import pytest

from ClimateGraph.utils.general_utils import (
    CRSEnum,
    ReductionMethodEnum,
    TimeBucketEnum,
    TimestepEnum,
    manage_path,
    manage_time_interval,
)


class TestManageTimeInterval:
    def test_dash_separator_dayfirst(self):
        # Daily range: each endpoint expands to its full bucket, so the end
        # covers all of Mar 31st (start of next day minus 1 ns).
        start, end = manage_time_interval("1/2/2019 - 31/3/2019")
        assert start == pd.Timestamp(2019, 2, 1)
        assert end == pd.Timestamp("2019-03-31 23:59:59.999999999")

    def test_to_separator(self):
        start, end = manage_time_interval("1/1/2020 to 1/2/2020")
        assert start.month == 1 and end.month == 2

    def test_single_date_spans_its_day(self):
        # A lone day-resolution date means the whole day.
        start, end = manage_time_interval("30/1/2001")
        assert start == pd.Timestamp("2001-01-30 00:00:00")
        assert end == pd.Timestamp("2001-01-30 23:59:59.999999999")

    def test_subdaily_range_keeps_endpoints(self):
        # Hour-or-finer resolutions are exact points: no bucket expansion.
        start, end = manage_time_interval("30/1/2001 10:00:00-30/1/2001 22:00:00")
        assert start == pd.Timestamp("2001-01-30 10:00:00")
        assert end == pd.Timestamp("2001-01-30 22:00:00")

    def test_month_resolution_spans_month(self):
        start, end = manage_time_interval("3/2019")
        assert start == pd.Timestamp("2019-03-01 00:00:00")
        assert end == pd.Timestamp("2019-03-31 23:59:59.999999999")

    def test_year_resolution_spans_year(self):
        start, end = manage_time_interval("2001")
        assert start == pd.Timestamp("2001-01-01 00:00:00")
        assert end == pd.Timestamp("2001-12-31 23:59:59.999999999")

    def test_mixed_resolution_warns_not_raises(self, caplog):
        with caplog.at_level(logging.WARNING):
            start, end = manage_time_interval("30/1/2001 - 31/1/2001 10:00:00")
        assert any(
            "different temporal resolutions" in rec.message for rec in caplog.records
        )
        # best-effort: coarse start floored, fine end kept as a point.
        assert start == pd.Timestamp("2001-01-30 00:00:00")
        assert end == pd.Timestamp("2001-01-31 10:00:00")

    def test_invalid_single_token_raises(self):
        # No separator -> treated as a single date; unparseable text still raises.
        with pytest.raises(ValueError):
            manage_time_interval("just a single date")

    def test_invalid_date_raises(self):
        # dateutil.parser.parse raises ParserError (a ValueError subclass) on garbage.
        with pytest.raises(ValueError):
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

    def test_sort_kwarg_sorts_results(self, tmp_path):
        for name in ("c.nc", "a.nc", "b.nc"):
            (tmp_path / name).write_bytes(b"")
        # Pass as an explicit list in non-sorted order.
        files = [str(tmp_path / n) for n in ("c.nc", "a.nc", "b.nc")]
        sorted_result = manage_path(files, sort=True)
        assert [p.name for p in sorted_result] == ["a.nc", "b.nc", "c.nc"]

    def test_sort_kwarg_warns_when_input_was_unordered(self, tmp_path, caplog):
        for name in ("c.nc", "a.nc"):
            (tmp_path / name).write_bytes(b"")
        files = [str(tmp_path / n) for n in ("c.nc", "a.nc")]
        with caplog.at_level(logging.WARNING):
            manage_path(files, sort=True)
        assert any(
            "not in lexicographic order" in rec.message for rec in caplog.records
        )

    def test_sort_kwarg_silent_when_input_already_ordered(self, tmp_path, caplog):
        for name in ("a.nc", "b.nc"):
            (tmp_path / name).write_bytes(b"")
        files = [str(tmp_path / n) for n in ("a.nc", "b.nc")]
        with caplog.at_level(logging.WARNING):
            manage_path(files, sort=True)
        assert not any(
            "not in lexicographic order" in rec.message for rec in caplog.records
        )

    def test_default_does_not_sort(self, tmp_path):
        for name in ("c.nc", "a.nc"):
            (tmp_path / name).write_bytes(b"")
        files = [str(tmp_path / n) for n in ("c.nc", "a.nc")]
        # Default sort=False preserves input order.
        assert [p.name for p in manage_path(files)] == ["c.nc", "a.nc"]


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
