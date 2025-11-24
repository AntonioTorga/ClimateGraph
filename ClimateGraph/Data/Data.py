from abc import ABC, abstractmethod
from __future__ import annotations
from pathlib import Path
import numpy as np
import xarray as xr


class Data(ABC):
    def __init__(
        self, name: str, path: Path | list[Path], vars: str | list[str] = None
    ):
        self.name = name
        self.path = path
        self.obj = None
        self.geom = None
        self.crs = None
        domain_cache = dict()
        collection = dict()

        # Might be that vars is also required when creating a Data object. If not, add a add_vars function
        # that checks if the added vars exist. Actually, yeah TODO: that because when the parser runs through the yaml
        # it may need to add the vars.
        self.vars = vars
        if self.vars is not None:
            self._scan_obj(vars=self.vars)

    @abstractmethod
    def read_obj(self, vars: list[str] | None = None):
        pass

    @abstractmethod
    def _set_geom(self):
        pass

    def _scan_obj(self, vars: list | str) -> bool:
        glimpse_path = self.path
        if isinstance(glimpse_path, list):
            glimpse_path = glimpse_path[0]
        glimpse = xr.open_dataset(glimpse_path)
        for var_name in vars:
            if not var_name in glimpse.data_vars.keys():
                raise KeyError(f"Variable {var_name} not in {self.name} dataset.")

    def get_obj(self) -> xr.Dataset:
        if self.obj == None:
            self.load_obj(vars=self.vars)
        return self.obj

    def get_geom(self):
        if self.geom == None:
            self._set_geom()
        return self.geom

    def get_var(
        self, var_names: list[str] | str, as_array: bool = False
    ) -> dict[str, xr.DataArray] | xr.DataArray | dict[str, np.array] | np.array:
        obj = self.get_obj()

        if isinstance(var_names, str):
            var_names = [var_names]
        missing_vars = [i for i in var_names if i not in obj.data_vars.keys()]
        if len(missing_vars) > 0:
            raise KeyError(f"Variables {missing_vars} not in {self.name} dataset.")

        # Keeps the initial var_names because if one is missing function gets interrupted, and will never reach here.
        vars = {var: obj.data_vars[var] for var in var_names}
        if as_array:
            vars = {var: array.as_numpy() for var, array in vars.items()}

        # If only one var required return directly. Maybe not a great choice could lead to Runtime errors.
        if len(vars) == 1:
            vars = list(vars.values())[0]

        return vars

    def get_coordinates(
        self, coord_names: list[str] | str, as_array: bool = False
    ) -> dict[str, xr.DataArray] | xr.DataArray | dict[str, np.array] | np.array:
        obj = self.get_obj()
        if isinstance(coord_names, str):
            coord_names = [coord_names]
        missing_coords = [i for i in coord_names if i not in obj.coords.keys()]
        if len(missing_coords) > 0:
            raise KeyError(f"Coordinates {missing_coords} not in {self.name} dataset.")

        # Keeps the initial coord_names because if one is missing function gets interrupted, and will never reach here.
        coords = {coord: obj.coords[coord] for coord in coord_names}
        if as_array:
            coords = {coord: array.as_numpy() for coord, array in coords.items()}

        # If only one coord required return directly. Maybe not a great choice could lead to Runtime errors.
        if len(coords) == 1:
            coords = list(coords.values())[0]
        return coords

    def add_to_collection(self, other: Data):
        pass
