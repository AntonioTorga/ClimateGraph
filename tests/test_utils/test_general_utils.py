import logging

import numpy as np
import pandas as pd
import pytest

from ClimateGraph.utils.general_utils import (
    CRSEnum,
    ExpandableModel,
    ReductionMethodEnum,
    TimeBucketEnum,
    TimestepEnum,
    expand,
    manage_path,
    manage_time_interval,
    normalize_time,
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


class TestNormalizeTime:
    def test_none_becomes_single_none_entry(self):
        assert normalize_time(None) == [None]

    def test_single_string_becomes_one_element_list(self):
        assert normalize_time("1/1/2019 - 1/2/2019") == ["1/1/2019 - 1/2/2019"]

    def test_list_passes_through_unchanged(self):
        entries = ["1/1/2019 - 1/2/2019", "1/3/2019 - 1/4/2019"]
        assert normalize_time(entries) is entries


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


class _Fan(ExpandableModel):
    """Two independent axes plus a field that must survive untouched."""

    expands = ("alpha", "beta")

    alpha: str | list[str] | None = None
    beta: int | list[int] | None = None
    unrelated: str = "fixed"


class _Mapped(ExpandableModel):
    """The name-to-unit mapping case."""

    expands = ("vars",)

    vars: str | list[str] | dict[str, str] | None = None


class _Gated(ExpandableModel):
    """An axis that only fans out on request, like a domain's one_for_each."""

    expands = ("values",)

    values: str | list[str] | None = None
    one_for_each: bool = False

    def expansion_gate(self, field):
        return self.one_for_each


class _Computed(ExpandableModel):
    """An axis whose values come from elsewhere, like a Points domain."""

    expands = ("chosen",)

    chosen: str | None = None
    points: list[str] = []

    def expansion_values(self, field):
        return list(self.points)


class TestExpand:
    def test_no_axes_yields_the_model_itself(self):
        class _Plain(ExpandableModel):
            value: int = 1

        model = _Plain()
        assert expand(model) == [({}, model)]

    def test_single_axis_scalarises(self):
        results = expand(_Fan(alpha=["a", "b"]))
        assert [slots["alpha"] for slots, _ in results] == ["a", "b"]
        # The copy holds a single value, not a one-element list: anything
        # downstream has no loop left to run.
        assert [copy.alpha for _, copy in results] == ["a", "b"]

    def test_product_of_two_axes(self):
        results = expand(_Fan(alpha=["a", "b"], beta=[1, 2, 3]))
        assert len(results) == 6
        assert [(s["alpha"], s["beta"]) for s, _ in results] == [
            ("a", 1),
            ("a", 2),
            ("a", 3),
            ("b", 1),
            ("b", 2),
            ("b", 3),
        ]

    def test_non_axis_fields_survive(self):
        _, copy = expand(_Fan(alpha=["a"], unrelated="kept"))[0]
        assert copy.unrelated == "kept"

    def test_scalar_and_none_yield_one_copy(self):
        assert len(expand(_Fan(alpha="solo"))) == 1
        assert expand(_Fan())[0][1].alpha is None

    def test_empty_list_is_not_an_axis(self):
        # Zero figures would be the wrong reading of `domains: []`.
        results = expand(_Fan(alpha=[]))
        assert len(results) == 1
        assert results[0][1].alpha == []

    def test_mapping_keeps_its_unit_and_names_its_key(self):
        results = expand(_Mapped(vars={"PM25": "ug/m**3", "NO2": "ppb"}))
        assert [copy.vars for _, copy in results] == [
            {"PM25": "ug/m**3"},
            {"NO2": "ppb"},
        ]
        assert [slots["vars"] for slots, _ in results] == ["PM25", "NO2"]

    def test_closed_gate_suppresses_the_axis(self):
        grouped = expand(_Gated(values=["a", "b"], one_for_each=False))
        assert len(grouped) == 1
        assert grouped[0][1].values == ["a", "b"]

        each = expand(_Gated(values=["a", "b"], one_for_each=True))
        assert [copy.values for _, copy in each] == ["a", "b"]

    def test_values_may_come_from_elsewhere(self):
        results = expand(_Computed(points=["centro", "sur"]))
        assert [copy.chosen for _, copy in results] == ["centro", "sur"]

    def test_copies_are_independent_of_the_original(self):
        original = _Fan(alpha=["a", "b"])
        expand(original)
        assert original.alpha == ["a", "b"]
