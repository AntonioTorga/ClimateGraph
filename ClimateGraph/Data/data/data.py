from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np
import xarray as xr


class Data(ABC):
    registry: dict[str, type["Data"]] = {}
    type_aliases: list[str] = list()

    # Allows for self registering, and alias registering, for then looking up the right Data Class.
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Data.registry[cls.__name__.lower()] = cls

        for alias in getattr(cls, "type_aliases", []):
            Data.registry[alias.lower()] = cls
        print(f"Registry: \n{Data.registry}")

    def __init__(
        self, name: str, path: Path | list[Path], vars: str | list[str] | None = None
    ):
        self.name = name
        self.path = path

        self.reader = None
        self.obj = None
        self.geom = None
        self.bbox = None  # minlon, minlat, maxlon, maxlat
        self.crs = (
            None  # Not sure if necessary, because it doesn't really exist in many cases
        )

        domain_cache = dict()

        self.vars = vars

    @abstractmethod
    def load_obj(self, vars: list[str] | None = None):
        pass

    @abstractmethod
    def _set_geom(self):
        pass

    def _scan_obj(self, vars: list | str) -> bool:
        glimpse_path = self.path
        if isinstance(glimpse_path, list):
            glimpse_path = glimpse_path[0]
        with xr.open_dataset(glimpse_path) as glimpse:
            for var_name in vars:
                if not var_name in glimpse.data_vars.keys():
                    raise KeyError(f"Variable {var_name} not in {self.name} dataset.")

    @property
    def obj(self) -> xr.Dataset:
        if self.obj == None:
            self.load_obj(vars=self.vars)
        lons, lats = self.get_coordinates(["longitude", "latitude"])
        self.bbox = (lons.min(), lats.min(), lons.max(), lats.max())
        return self.obj

    @property
    def geom(self):
        if self.geom == None:
            self._set_geom()
        return self.geom

    @property
    def vars(self):
        return self.vars

    @vars.setter
    def vars(self, vars):
        self._scan_obj(vars=self.vars)
        self.vars = vars

    def get_var(
        self, var_names: list[str] | str, as_array: bool = False
    ) -> list[xr.DataArray] | xr.DataArray | list[np.ndarray] | np.ndarray:
        obj = self.get_obj()

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
