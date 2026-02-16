import xarray as xr


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
