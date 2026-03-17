from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np
import xarray as xr
import cartopy.crs as ccrs
from typing import Dict
import pint_xarray
from pint import Quantity
from typing import Callable, Any, List, Dict
from pyresample import kd_tree
from datetime import datetime


from ClimateGraph.reader import Reader
from ClimateGraph.utils.dataset_utils import time_resampling, change_unit
from ClimateGraph.utils.general_utils import manage_time_interval, ReductionMethodEnum


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
        return type.lower() in cls.registry

    @classmethod
    def create(
        cls,
        name: str,
        topology: str,
        reader: str,
        path: Path | List[Path],
        vars: Dict[str, Dict[str, str]],
        crs: ccrs,
        reader_kwargs: Dict,
    ):
        data_cls = cls.get_data_subclass(topology)
        reader_cls = Reader.get_reader_subclass(topology, reader)
        return data_cls(name, path, vars, reader_cls, crs, reader_kwargs=reader_kwargs)

    def __init__(
        self,
        name: str,
        path: Path | list[Path],
        vars: Dict[str, Dict[str, str]],
        reader: Reader,
        crs: ccrs.CRS,
        reader_kwargs: Dict[str, Any] | None = None,
    ):
        # This seems weird and unnecesary, but i'll keep it for now
        self.reader = reader
        self.reader_kwargs = {} if reader_kwargs is None else reader_kwargs

        # Going to be set later
        self._obj = None
        self._geom = None
        self._vars = vars
        self._path = None
        self._bbox = None  # minlon, minlat, maxlon, maxlat
        self._dims = None
        self.resampled = None

        # Provided by user
        self.name = name
        self.path = path
        self.crs = crs

    @abstractmethod
    def _set_geom(self):
        pass

    @property
    def obj(self) -> xr.Dataset:
        if self._obj == None:
            self.load_obj()
        return self._obj

    @property
    def geom(self):
        if self._geom == None:
            self._set_geom()
        return self._geom

    @property
    def vars(self):
        return self._vars

    # TODO: decide if it's worth adding the scan_obj, for now this doesn't exist because i don't want anyone being able to set vars except the init
    # @vars.setter
    # def vars(self, vars):
    #     var_names = [var.get("name") for _, var in vars.items()]
    #     # self._scan_obj(vars=var_names)     #     self._vars = vars

    @property
    def dims(self):
        if self._dims is None:
            self._dims = dict(self.obj.dims)
        return self._dims

    @property
    def bbox(self):
        if self._bbox is None:
            lons, lats = self.get_coordinates(["longitude", "latitude"])
            self._bbox = (lons.min(), lats.min(), lons.max(), lats.max())
        return self._bbox

    def load_obj(self):
        self._obj = self.reader.open_mfdataset(
            self.path, self.vars, **self.reader_kwargs
        )
        return self._obj

    def _scan_obj(self, vars: list | str) -> bool:
        glimpse_path = self.path[0] if isinstance(self.path, list) else self.path
        if isinstance(glimpse_path, list):
            glimpse_path = glimpse_path[0]
        with xr.open_dataset(glimpse_path) as glimpse:
            for var_name in vars:
                if not var_name in glimpse.data_vars.keys():
                    raise KeyError(f"Variable {var_name} not in {self.name} dataset.")

    # The var_name is the variable name not native to the file but as how it is referred in vars
    def get_var(
        self,
        var_name: str,
        in_unit: str | None = None,
        reduction_func: str | None = None,
        keep_dims: str | list[str] | None = None,
        reduction_dims: str | list[str] | None = None,
        as_array: bool = False,
    ):
        if var_name not in self.vars:
            raise KeyError(f"Variable {var_name} not defined for dataset {self.name}.")

        xa = self.obj.data_vars[var_name]

        if reduction_func is not None:
            reduction_func = (
                ReductionMethodEnum(reduction_func).func
                if isinstance(reduction_func, str)
                else reduction_func
            )
            if reduction_dims is None and keep_dims is not None:
                reduction_dims = list(set(self.dims) - set(keep_dims))
            xa = xa.reduce(reduction_func, reduction_dims)

        if in_unit is not None:
            src_unit = self.vars[var_name]["unit"]
            dst_unit = in_unit
            xa = change_unit(xa, src_unit, dst_unit)

        if as_array:
            xa = xa.to_numpy()

        return xa

    def get_coordinates(
        self,
        coord_names: list[str] | str,
        two_dim: bool = False,
        as_array: bool = False,
    ) -> list[xr.DataArray] | xr.DataArray | list[np.ndarray] | np.ndarray:
        obj = self.obj
        if isinstance(coord_names, str):
            coord_names = [coord_names]
        missing_coords = [i for i in coord_names if i not in obj.coords.keys()]
        if len(missing_coords) > 0:
            raise KeyError(f"Coordinates {missing_coords} not in {self.name} dataset.")

        # Keeps the initial coord_names because if one is missing function gets interrupted, and will never reach here.
        coords = [obj.coords[coord] for coord in coord_names]
        if as_array:
            coords = [array.to_numpy() for array in coords]

        # If only one coord required return directly. Maybe not a great choice could lead to Runtime errors.
        if len(coords) == 1:
            coords = coords[0]
        return coords

    # Might need to become a whole pairing engine in some time. But for now this will do
    def resample_vars(
        self,
        other: "Data",
        vars: str | List[str] | Dict[str, str],
        timestep: str | None = None,
        time_interval: str | None = None,
        radius_of_influence: int | None = None,
        # reduction_dims: str | List[str] | None = None, reduction_func: Callable | None = None
    ) -> xr.DataArray | xr.Dataset:
        if isinstance(vars, str):
            vars = [vars]

        src_geom = other.geom
        dst_geom = self.geom

        valid_input, valid_output, index_array, dist_array = kd_tree.get_neighbour_info(
            src_geom,
            dst_geom,
            radius_of_influence=radius_of_influence,
            neighbours=1,
        )

        new_vars = []
        for var in vars:
            var_dst_dims = self.get_var(var).sizes
            var_src = other.get_var(var)

            # assume that the caller wants the var either in a specified unit, or the unit of the base of resampling.
            dst_unit = (
                self.vars[var]["unit"] if isinstance(vars, list | str) else vars[var]
            )
            src_unit = other.vars[var]["unit"]
            var_src = change_unit(var_src, src_unit, dst_unit)

            # time resampling
            var_src = time_resampling(
                var_src, timestep=timestep, time_interval=time_interval
            )

            def _resample(x):
                return kd_tree.get_sample_from_neighbour_info(
                    "nn",
                    dst_geom.shape,
                    x,
                    valid_input,
                    valid_output,
                    index_array,
                    dist_array,
                    fill_value=np.nan,
                )

            resampled = xr.apply_ufunc(
                _resample,
                var_src,
                input_core_dims=[
                    [d for d in var_src.dims if d != "time"]
                ],  # remove time from core dims so it loops over just time
                output_core_dims=[
                    [d for d in var_dst_dims.keys() if d != "time"]
                ],  # Produces a new array with the new geom minus time
                vectorize=True,
                dask="parallelized",
                output_dtypes=[var_src.dtype],
                output_sizes={
                    name: value
                    for name, value in var_dst_dims.items()
                    if name != "time"
                },
            )

            if self.resampled is None:
                self.resampled = self.obj.drop_vars(list(self.obj.data_vars))
                self.resampled = time_resampling(
                    self.resampled, timestep=timestep, time_interval=time_interval
                )

            new_name = f"{var}__{other.name}"
            self.resampled[new_name] = (var_dst_dims, resampled.data)
            new_vars.append(new_name)
        return self.resampled[new_vars]
