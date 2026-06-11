import numpy as np
import pytest
import xarray as xr

from ClimateGraph.utils.dataset_utils import (
    apply_operation,
    change_unit,
    time_resampling,
)
from ClimateGraph.utils.general_utils import ReductionMethodEnum


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
