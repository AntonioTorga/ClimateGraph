import numpy as np
import xarray as xr

from ClimateGraph.utils.dataset_utils import (
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
