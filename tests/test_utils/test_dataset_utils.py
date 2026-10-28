import numpy as np
import pytest
import xarray as xr
from pandas.tseries.frequencies import to_offset

from ClimateGraph.utils.dataset_utils import (
    apply_operation,
    change_unit,
    dim_reduction,
    drop_nan_points,
    time_resampling,
)
from ClimateGraph.utils.general_utils import ReductionMethodEnum, TimestepEnum


class TestHistory:
    def test_time_resampling_interval_records(self, regular_grid_dataset):
        result = time_resampling(
            regular_grid_dataset, time_interval="2/1/2019 - 4/1/2019"
        )
        assert "history" in result.attrs
        assert any("selected time interval" in e for e in result.attrs["history"])

    def test_time_resampling_timestep_records(self, regular_grid_dataset):
        result = time_resampling(regular_grid_dataset, timestep="2D")
        assert any("resampled time to 2D" in e for e in result.attrs["history"])

    def test_change_unit_records(self):
        import numpy as np

        xa = xr.DataArray(np.array([273.15]), dims="time", name="T")
        out = change_unit(xa, "kelvin", "degC")
        assert "history" in out.attrs
        assert any("kelvin" in e and "degC" in e for e in out.attrs["history"])

    def test_apply_operation_records(self):
        import numpy as np

        xa = xr.DataArray(np.array([1.0, 2.0]), dims="time", name="x")
        out = apply_operation("*2", {"x": xa})
        assert "history" in out.attrs
        assert any("computed:" in e for e in out.attrs["history"])

    def test_resample_vars_records(self, regular_grid_data, point_surface_data):
        result = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=500_000
        )
        assert "history" in result.attrs
        assert any("spatially resampled" in e for e in result.attrs["history"])


class TestDimReduction:
    def test_isel_drops_dim(self):
        ds = xr.Dataset({"T": (("time", "z", "x"), np.ones((3, 4, 5)))})
        result = dim_reduction(ds, {"z": {"method": "isel", "value": 0}})
        assert "z" not in result.dims
        assert result["T"].shape == (3, 5)

    def test_sel_selects_label(self):
        da = xr.DataArray(
            np.arange(12).reshape(3, 4),
            dims=("time", "z"),
            coords={"z": [0.0, 1.0, 2.0, 3.0]},
        )
        result = dim_reduction(da, {"z": {"method": "sel", "value": 2.0}})
        assert "z" not in result.dims

    def test_string_shorthand_reduces(self):
        ds = xr.Dataset({"T": (("time", "z"), np.ones((3, 4)))})
        result = dim_reduction(ds, {"z": "mean"})
        assert "z" not in result.dims

    def test_skips_missing_dim(self):
        ds = xr.Dataset({"T": (("time", "x"), np.ones((3, 5)))})
        result = dim_reduction(ds, {"z": "mean"})
        assert set(result.dims) == {"time", "x"}

    def test_records_history(self):
        ds = xr.Dataset({"T": (("time", "z"), np.ones((3, 4)))})
        result = dim_reduction(ds, {"z": {"method": "isel", "value": 0}}, name="test")
        assert any("selected z=0" in e for e in result.attrs["history"])

    def test_get_var_with_dim_reduce(self, regular_grid_data):
        xa = regular_grid_data.get_var("Temperatura")
        assert "y" in xa.dims and "x" in xa.dims
        xa_reduced = regular_grid_data.get_var(
            "Temperatura", dim_reduce={"y": {"method": "isel", "value": 0}}
        )
        assert "y" not in xa_reduced.dims
        assert "x" in xa_reduced.dims


class TestTimeResampling:
    def test_time_interval_slices(self, regular_grid_dataset):
        sliced = time_resampling(
            regular_grid_dataset, time_interval="2/1/2019 - 4/1/2019"
        )
        assert sliced.sizes["time"] == 3
        assert str(sliced["time"].values[0])[:10] == "2019-01-02"

    def test_timestep_resamples_with_default_mean(self, regular_grid_dataset):
        # Default is mean; daily → 2-daily should halve the steps.
        result = time_resampling(regular_grid_dataset, timestep="2D")
        assert result.sizes["time"] == 3

    def test_timestep_accepts_the_enum_not_just_a_string(self, regular_grid_dataset):
        # What a parsed control file actually supplies. pandas resolves common
        # aliases from a cache that tolerates a str subclass and type-checks
        # strictly otherwise, so passing the member worked only by alias.
        result = time_resampling(regular_grid_dataset, timestep=TimestepEnum.daily)
        assert result.sizes["time"] == regular_grid_dataset.sizes["time"]

    @pytest.mark.parametrize("unit", list(TimestepEnum))
    def test_every_timestep_is_a_valid_pandas_frequency(self, unit):
        # "Q" and "Y" were removed in pandas 3.0 in favour of "QE"/"YE", so a
        # member can be accepted by the config and still fail at resample time.
        assert to_offset(unit.value) is not None

    def test_timestep_with_min_reduction(self, regular_grid_dataset):
        result = time_resampling(
            regular_grid_dataset,
            timestep="2D",
            reduction_method=ReductionMethodEnum.min,
        )
        # Each 2-day bucket should equal the per-bucket min — verify on Temperatura
        baseline = (
            regular_grid_dataset["Temperatura"].resample(time="2D").reduce(np.nanmin)
        )
        xr.testing.assert_allclose(result["Temperatura"], baseline)

    def test_none_args_is_identity(self, regular_grid_dataset):
        result = time_resampling(regular_grid_dataset)
        xr.testing.assert_identical(result, regular_grid_dataset)


class TestChangeUnit:
    def test_kelvin_to_celsius(self):
        xa = xr.DataArray(
            np.array([273.15, 283.15, 293.15]),
            dims="time",
            name="T",
        )
        out = change_unit(xa, "kelvin", "degC")
        np.testing.assert_allclose(out.values, [0.0, 10.0, 20.0])

    def test_same_unit_short_circuits(self):
        xa = xr.DataArray(np.array([1.0, 2.0]), dims="time", name="T")
        out = change_unit(xa, "kelvin", "kelvin")
        assert out is xa  # short-circuit returns the same object

    def test_coords_preserved(self):
        xa = xr.DataArray(
            np.array([0.0, 100.0]),
            dims="time",
            coords={"time": [0, 1]},
            name="T",
        )
        out = change_unit(xa, "kelvin", "degC")
        assert "time" in out.coords


class TestApplyOperation:
    def _xa(self):
        return xr.DataArray(
            np.array([1.0, 2.0, 3.0]),
            dims="time",
            coords={"time": [0, 1, 2]},
            name="PM25",
        )

    def _vars(self):
        return {"x": self._xa()}

    def test_leading_operator_shorthand_multiply(self):
        out = apply_operation("*3", self._vars())
        np.testing.assert_allclose(out.values, [3.0, 6.0, 9.0])

    def test_leading_operator_divide(self):
        out = apply_operation("/2", self._vars())
        np.testing.assert_allclose(out.values, [0.5, 1.0, 1.5])

    def test_power_shorthand(self):
        # "**2" starts with "*", so the shorthand expands to "x**2".
        out = apply_operation("**2", self._vars())
        np.testing.assert_allclose(out.values, [1.0, 4.0, 9.0])

    def test_explicit_x_expression(self):
        out = apply_operation("x / 48 * 24.45", self._vars())
        np.testing.assert_allclose(out.values, np.array([1.0, 2.0, 3.0]) / 48 * 24.45)

    def test_negative_constant_via_unary(self):
        # "*-0.8" -> "x*-0.8"; the -0.8 is UnaryOp(USub, 0.8), not a literal.
        out = apply_operation("*-0.8", self._vars())
        np.testing.assert_allclose(out.values, np.array([1.0, 2.0, 3.0]) * -0.8)

    def test_name_and_coords_preserved(self):
        out = apply_operation("*3", self._vars())
        assert out.name == "PM25"
        assert "time" in out.coords

    def test_references_other_variables_by_name(self):
        a = xr.DataArray(np.array([1.0, 2.0]), dims="time", name="A")
        b = xr.DataArray(np.array([3.0, 4.0]), dims="time", name="B")
        out = apply_operation("A + B", {"A": a, "B": b})
        np.testing.assert_allclose(out.values, [4.0, 6.0])

    def test_unknown_name_raises(self):
        with pytest.raises(ValueError, match="unknown variable 'y'"):
            apply_operation("x + y", self._vars())

    @pytest.mark.parametrize(
        "bad",
        ["__import__('os')", "x.values", "foo * 2", "x + y"],
    )
    def test_rejects_non_arithmetic(self, bad):
        with pytest.raises(ValueError):
            apply_operation(bad, self._vars())


class TestDropNanPoints:
    def test_drops_only_nan_valued_entries(self):
        lons = np.array([1.0, 2.0, 3.0])
        lats = np.array([10.0, 20.0, 30.0])
        vals = np.array([5.0, np.nan, 7.0])

        out_lons, out_lats, out_vals = drop_nan_points(lons, lats, vals)

        assert out_lons.tolist() == [1.0, 3.0]
        assert out_lats.tolist() == [10.0, 30.0]
        assert out_vals.tolist() == [5.0, 7.0]

    def test_no_nans_returns_everything(self):
        lons, lats, vals = (np.array([1.0, 2.0]),) * 3
        out_lons, _, _ = drop_nan_points(lons, lats, vals)
        assert out_lons.tolist() == [1.0, 2.0]

    def test_all_nan_returns_empty(self):
        lons = np.array([1.0, 2.0])
        lats = np.array([3.0, 4.0])
        vals = np.array([np.nan, np.nan])
        out_lons, out_lats, out_vals = drop_nan_points(lons, lats, vals)
        assert out_lons.size == out_lats.size == out_vals.size == 0
