import xarray as xr

from .general_utils import manage_time_interval, ReductionMethodEnum

import pint_xarray
from pint import Quantity

# TODO: make this into accessors

def variable_aggregation(ds: xr.Dataset, aggregation_dict: dict) -> xr.Dataset:
    # key: new variable
    # value: dict with dict(old variable : ponderations to sum)
    new_vars = dict()

    for new_var, ponderations in aggregation_dict.items():
        xa = None
        for name_var, ponderation in ponderations.items():
            if xa is None:
                xa = ds[name_var].copy() * ponderation
            else:
                xa += ds[name_var] * ponderation

        new_vars[new_var] = xa

    return ds.assign(new_vars)

def time_resampling(
    ds: xr.Dataset | xr.DataArray,
    timestep: str | None = None,
    time_interval: str | None = None,
    reduction_method: ReductionMethodEnum = ReductionMethodEnum.mean
) -> xr.Dataset | xr.DataArray:
    if time_interval is not None:
        start, end = manage_time_interval(time_interval)
        ds = ds.sel({"time": slice(start, end)})
    if timestep is not None:
        ds = getattr(ds.resample(time=timestep), reduction_method.value)()
    return ds

def change_unit(xa: xr.DataArray, src_unit: str, dst_unit: str):
    if src_unit == dst_unit: return xa # No sense on performing any operations if it is already in the desired unit.

    xa_coords = list(xa.coords.keys())
    var_name = xa.name
    xa = xa.reset_coords(drop=False)
    xa[var_name] = xa[var_name].pint.quantify(src_unit)
    xa[var_name] = xa[var_name].pint.to(dst_unit)
    xa[var_name] = xa[var_name].pint.dequantify()
    xa = xa.set_coords(xa_coords)
    return xa[var_name]