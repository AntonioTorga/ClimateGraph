from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np
import xarray as xr
import cartopy.crs as ccrs
from typing import Dict
import pint_xarray
from pint import Quantity
from typing import Callable

from ClimateGraph.reader import Reader

REDUCTION_FUNCS = {"min": np.nanmin, "max": np.nanmax, "mean": np.nanmean}


class Data(ABC):
    registry: dict[str, type["Data"]] = {}
    type_aliases: list[str] = list()

    # Allows for self registering, and alias registering, for then looking up the right Data Class.
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Data.registry[cls.__name__.lower()] = cls

        for alias in getattr(cls, "type_aliases", []):
            Data.registry[alias.lower()] = cls

    @classmethod
    def get_data_subclass(cls, name: str):
        _name = name.lower()
        try:
            data_class = cls.registry[_name]
        except KeyError:
            raise ValueError(
                f"No type named {name} recognized. Options are {Data.registry.keys()} (case insensitive)."
            )
        return data_class

    @classmethod
    def check_topology_type(cls, type: str):
        return type in cls.registry

    def __init__(
        self,
        name: str,
        path: Path | list[Path],
        vars: Dict[str, dict],
        reader: Reader,
        crs: ccrs.CRS,
        reader_kwargs: dict | None = None,
    ):
        # This seems weird and unnecesary, but i'll keep it for now
        self.reader = reader
        self.reader_kwargs = {} if reader_kwargs is None else reader_kwargs

        # Going to be set later
        self._obj = None
        self._geom = None
        self._vars = None
        self._path = None
        self.bbox = None  # minlon, minlat, maxlon, maxlat
        self.dims = None
        self.resampled = None

        # Provided by user
        self.name = name
        self.path = path
        self.crs = (
            crs  # Not sure if necessary, because it doesn't really exist in many cases
        )
        self.vars = vars

    @abstractmethod
    def _set_geom(self):
        pass

    @property
    def obj(self) -> xr.Dataset:
        if self._obj == None:
            self.load_obj(vars=self.vars)
        lons, lats = self.get_coordinates(["longitude", "latitude"])
        self.bbox = (lons.min(), lats.min(), lons.max(), lats.max())
        self.dims = dict(self._obj.dims)
        return self._obj

    @property
    def geom(self):
        if self._geom == None:
            self._set_geom()
        return self._geom

    @property
    def vars(self):
        return self._vars

    def load_obj(self):
        self.obj = self.reader.open_mfdataset(self.path, self.vars, self.reader_kwargs)
        return self.obj

    def _scan_obj(self, vars: list | str) -> bool:
        glimpse_path = self.path[0] if isinstance(self.path, list) else self.path
        if isinstance(glimpse_path, list):
            glimpse_path = glimpse_path[0]
        with xr.open_dataset(glimpse_path) as glimpse:
            for var_name in vars:
                if not var_name in glimpse.data_vars.keys():
                    raise KeyError(f"Variable {var_name} not in {self.name} dataset.")

    @vars.setter
    def vars(self, vars):
        var_names = [var.get("name") for _, var in vars.items()]
        self._scan_obj(vars=var_names)
        self._vars = vars

    # The reduction kwarg is in the following structure: str(name of reduction func in REDUCTION_FUNCS), str | list[str] (dims to reduce))
    # The var_name is the variable name not native to the file but as how it is referred in vars
    def get_var(
        self,
        var_name: str,
        in_unit: str | None = None,
        reduction_func: str | Callable | None = None,
        reduction_dims: str | list[str] | None = None,
        as_array: bool = False,
    ):
        if var_name not in self.vars:
            raise KeyError(f"Variable {var_name} not defined for dataset {self.name}.")
        obj_var_name, obj_var_unit = (
            self.vars[var_name]["name"],
            self.vars[var_name]["unit"],
        )
        xa = self.obj.data_vars[obj_var_name]

        if (reduction_func is not None) and (reduction_dims is not None):
            reduction_func = (
                REDUCTION_FUNCS[reduction_func]
                if isinstance(reduction_func, str)
                else reduction_func
            )
            xa = xa.reduce(reduction_func, reduction_dims)

        if in_unit is not None:

            xa_coords = list(xa.coords.keys())
            xa = xa.reset_coords(drop=False)
            xa = xa.pint.quantify(obj_var_unit)
            xa = xa.pint.to(in_unit)
            xa = xa.pint.dequantify()
            xa = xa.set_coords(xa_coords)

        if as_array:
            xa = xa.values

        return xa

    def get_coordinates(
        self, coord_names: list[str] | str, as_array: bool = False
    ) -> list[xr.DataArray] | xr.DataArray | list[np.ndarray] | np.ndarray:
        obj = self.get_obj()
        if isinstance(coord_names, str):
            coord_names = [coord_names]
        missing_coords = [i for i in coord_names if i not in obj.coords.keys()]
        if len(missing_coords) > 0:
            raise KeyError(f"Coordinates {missing_coords} not in {self.name} dataset.")

        # Keeps the initial coord_names because if one is missing function gets interrupted, and will never reach here.
        coords = [obj.coords[coord] for coord in coord_names]
        if as_array:
            coords = [array.as_numpy() for array in coords]

        # If only one coord required return directly. Maybe not a great choice could lead to Runtime errors.
        if len(coords) == 1:
            coords = coords[0]
        return coords

    def resample_var(self, other: "Data", var: str, method: str = "nn"):
        var_1 = self.get_var(var)
