from ..reader import Reader

from pathlib import Path
import xarray as xr


class DefaultRegularGridReader(Reader):

    @staticmethod
    def open_mfdataset(
        files: list[Path] | Path, var_list: list[str] = None, **kwargs
    ) -> xr.Dataset:

        rename_dict = kwargs.get("rename")

        datasets = []
        for file in files:
            datasets.append(xr.open_dataset(file))

        drop_data_vars = (
            set(list(datasets[0].data_vars)) - set(var_list)
            if var_list != None
            else set()
        )

        for i, ds in enumerate(datasets):
            ds = ds.drop_vars(drop_data_vars, errors="ignore")
            if rename_dict is not None:
                ds = ds.rename(rename_dict)
            datasets[i] = ds

        xrds = xr.concat(datasets, "time")
        xrds = xrds.reset_coords()
        xrds = xrds.set_coords(["latitude", "longitude"])

        if variable_aggregation_dict := kwargs.get("variable_aggregation") is not None:
            xrds = DefaultRegularGridReader.variable_aggregation(
                xrds, variable_aggregation_dict
            )

        return xrds

    # TODO: more like ponderated sum, maybe useful to add other aggregation mechanisms
    @staticmethod
    def variable_aggregation(ds: xr.Dataset, aggregation_dict: dict) -> xr.Dataset:
        # key: new variable
        # value: dict with dict(old variable : ponderations to sum)
        new_vars = dict()

        for new_var, ponderations in aggregation_dict.items():
            xa = None
            for name_var, ponderation in ponderations.items():
                if xa is None:
                    xa = ds[name_var].copy * ponderation
                else:
                    xa += ds[name_var] * ponderation

            new_vars[new_var] = xa

        return ds.assign(new_vars)
