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
from ClimateGraph.domain import Domain
from ClimateGraph.utils.dataset_utils import time_resampling, change_unit
from ClimateGraph.utils.general_utils import manage_time_interval, ReductionMethodEnum


class Data(ABC):
    """The Data abstract class.

    A class that abstracts the core nature of environmental data, independent of the topology of the data.
    This class contains and implements attributes and methods common to all the Data that ClimateGraph is supposed to handle.
    """

    registry: dict[str, type["Data"]] = {}
    type_aliases: list[str] = list()

    # Allows for self registering, and alias registering, for then looking up the right Data Class.
    def __init_subclass__(cls, **kwargs):
        """__init_subclass__ This Dunder method is being used to dinamically register all inheriting classes from Data, this helps with Data creation."""
        super().__init_subclass__(**kwargs)
        Data.registry[cls.__name__.lower()] = cls

        for alias in getattr(cls, "type_aliases", []):
            Data.registry[alias.lower()] = cls

    @classmethod
    def get_data_subclass(cls, name: str):
        """get_data_subclass Method for getting a class object from a string, centralizes the lookup operation for further development of smart lookup.

        Parameters
        ----------
        name : str
            String to use for lookup in the Data registry

        Returns
        -------
        type
            Object of Data subclass requested

        Raises
        ------
        ValueError
            No subclass available for the requested string
        """
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
        """check_topology_type Method for checking if a string correlates to a Data subclass, meant to have the same lookup mechanism as get_data_subclass

        Parameters
        ----------
        type : str
            String to lookup in Data class registry.

        Returns
        -------
        boolean
            Boolean representing existence of a correlation between the provided string and a Data subclass.
        """
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
        """create Creation of a Data object with the adequate Data subclass

        Parameters
        ----------
        name : str
            Name of the object, used for reference inside ClimateGraph execution.
        topology : str
            Type of topology, used for lookup in the Data registry.
        reader : str
            Specific reader name used for reading the files that compose the data object. A reader must exist for the corresponding topology and reader name.
        path : Path | List[Path]
            Path or list of paths that compose the data object.
        vars : Dict[str, Dict[str, str]]
            Dictionary where keys are Variable names, and the value is another Dictionary with "name" (with the name of the variable in the files) and "unit" (with the "pint" unit name for this variable) keys.
        crs : Cartopy.CRS
            Cartopy Coordinate Reference System object
        reader_kwargs : Dict
            Other keyword arguments in Dict format passed directly to the Reader, allows for further reader specialization.

        Returns
        -------
        Data
            Data object created with the arguments in the adequate Data subclass
        """
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
        """__init__ Data initialization dunder method.

        Parameters
        ----------
        name : str
            Name for reference inside the ClimateGraph execution.
        path : Path | list[Path]
            Path or list of paths that compose the data objects
        vars : Dict[str, Dict[str, str]]
            Dictionary where keys are Variable names, and the value is another Dictionary with "name" (with the name of the variable in the files) and "unit" (with the "pint" unit name for this variable) keys.
        reader : Reader
            Specific reader object used for reading the files that compose the data object. A reader must exist for the corresponding topology and reader name.
        crs : ccrs.CRS
            Cartopy Coordinate Reference System object
        reader_kwargs : Dict[str, Any] | None, optional
            Other keyword arguments in Dict format passed directly to the Reader, allows for further reader specialization, by default None
        """
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

    def copy(self):
        """copy Create an exact copy of the object and return it. Used for domain application.

        Returns
        -------
        Data
            Exact replica of the Data object
        """
        new = self.__class__(
            self.name,
            self.path,
            self.vars,
            self.reader,
            self.crs,
            reader_kwargs=self.reader_kwargs,
        )
        new.obj = self._obj
        new._geom = self._geom
        new._bbox = self._bbox  # minlon, minlat, maxlon, maxlat
        new._dims = self._dims
        new.resampled = self.resampled

        return new

    @abstractmethod
    def _set_geom(self):
        """_set_geom Method for setting the Pyresample Geometry object used for resampling. Main method of the topology abstraction."""
        pass

    @property
    def obj(self) -> xr.Dataset:
        """obj Property getter method for getting the obj object. Used for lazy loading of Data objects.

        Returns
        -------
        xr.Dataset
            Xarray dataset of the Data object.
        """
        if self._obj == None:
            self.load_obj()
        return self._obj

    @obj.setter
    def obj(self, _obj: xr.Dataset):
        """obj Property setter method for getting the obj object. Used for lazy loading of Data objects. Takes care of removing precomputed data for the previous Dataset.

        Parameters
        ----------
        _obj : xr.Dataset
             Xarray Dataset object meant to be set in the Data object.
        """
        self._obj = _obj
        self._bbox = None
        self._geom = None
        self._dims = None

    @property
    def geom(self):
        if self._geom == None:
            self._set_geom()
        return self._geom

    @property
    def vars(self):
        """vars Property getter method for getting the vars.

        Returns
        -------
        Dict[str, Dict[str, str]]
            Dictionary where keys are Variable names, and the value is another Dictionary with "name" (with the name of the variable in the files) and "unit" (with the "pint" unit name for this variable) keys.
        """
        return self._vars

    # TODO: decide if it's worth adding the scan_obj, for now this doesn't exist because i don't want anyone being able to set vars except the init
    # @vars.setter
    # def vars(self, vars):
    #     var_names = [var.get("name") for _, var in vars.items()]
    #     # self._scan_obj(vars=var_names)     #     self._vars = vars

    @property
    def dims(self):
        """dims Property getter method for getting a dimension mapping (dimension name to dimension size).

        Returns
        -------
        Dict[str, int]
            Dictionary mapping dimension names to dimension size.
        """
        if self._dims is None:
            self._dims = dict(self.obj.sizes)
        return self._dims

    @property
    def bbox(self):
        """bbox Property getter method for getting a bounding box around the spatial data.

        Returns
        -------
        Tuple[float, float, float, float]
            Tuple representing (Minimum Longitude,  Minimum Latitude, Maximum Longitude, Maximum Latitude)
        """
        if self._bbox is None:
            lons, lats = self.get_coordinates(["longitude", "latitude"])
            self._bbox = (
                float(lons.min()),
                float(lats.min()),
                float(lons.max()),
                float(lats.max()),
            )
        return self._bbox

    def load_obj(self):
        """load_obj Load the actual data into the obj attribute, using the reader and reader_kwargs attributes.

        Returns
        -------
        xr.Dataset
            Xarray dataset of the Data object.
        """
        self._obj = self.reader.open_mfdataset(
            self.path, self.vars, **self.reader_kwargs
        )
        return self._obj

    def _scan_obj(self):
        """_scan_obj Method for quickly scanning the obj attribute for errors. Currently only checks if variables actually exist

        Raises
        ------
        ValueError
            Raises an error if anything is wrong with the obj attribute.
        """
        glimpse_path = self.path[0] if isinstance(self.path, list) else self.path
        if isinstance(glimpse_path, list):
            glimpse_path = glimpse_path[0]
        with xr.open_dataset(glimpse_path, chunks="auto") as glimpse:
            for var_name, var_dict in self.vars:
                if not var_dict["name"] in glimpse and not var_name in glimpse:
                    raise ValueError(f"Variable {var_name} not in {self.name} dataset.")

    # The var_name is the variable name not native to the file but as how it is referred in vars
    def get_var(
        self,
        var_name: str,
        in_unit: str | None = None,
        reduction_func: str | None = None,
        keep_dims: str | list[str] | None = None,
        reduction_dims: str | list[str] | None = None,
        as_array: bool = False,
    ) -> xr.DataArray | np.ndarray:
        """get_var Get variable from the obj attribute.

        Parameters
        ----------
        var_name : str
            Variable name.
        in_unit : str | None, optional
            Measure of unit in which to convert the variable, by default None
        reduction_func : str | None, optional
            name of function with which to reduce the variable dimensions, dimensions in reduction_dims or, that aren't in keep_dims arg. Works only if keep_dims or reduction_dims is also specified. By default None
        keep_dims : str | list[str] | None, optional
            Dimensions to keep after reducing the others with the reduction_func. Only works if reduction_func is not None. By default None
        reduction_dims : str | list[str] | None, optional
            Dimensions to reduce with the reduction_func. Only works if reduction_func is not None. By default None
        as_array : bool, optional
            Boolean representing if the resulting data will be returned in numpy.ndarray format, by default False

        Returns
        -------
        xr.DataArray | numpy.ndarray
            Variable obtained from the obj attribute. Processed if required.

        Raises
        ------
        KeyError
            If the variable can't be found in the obj object.
        """
        if var_name not in self.obj and self.vars[var_name]["name"] not in self.obj:
            raise KeyError(f"Variable {var_name} not defined for dataset {self.name}.")
        var_name = var_name if var_name in self.obj else self.vars[var_name]["name"]
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
        as_array: bool = False,
    ) -> list[xr.DataArray] | xr.DataArray | list[np.ndarray] | np.ndarray:
        """get_coordinates Get coordinate from the obj attribute.

        Parameters
        ----------
        coord_names : list[str] | str
            Coordinate name or names.
        as_array : bool, optional
            Boolean representing if the resulting data will be returned in numpy.ndarray format, by default False

        Returns
        -------
        list[xr.DataArray] | xr.DataArray | list[np.ndarray] | np.ndarray
            Coordinate(s) obtained from the obj attribute. Processed if required.

        Raises
        ------
        KeyError
            If a coordinate can't be found in the obj object.
        """
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
        radius_of_influence: int = 10000,
        # reduction_dims: str | List[str] | None = None, reduction_func: Callable | None = None
    ) -> xr.DataArray | xr.Dataset:
        """resample_vars Resample the requested vars using Pyresample and the geom attributes. Until now only NearestNeighbour method is being used.

        Parameters
        ----------
        other : Data
            Other data object to resample into the "self" geometry.
        vars : str | List[str] | Dict[str, str]
            Variable name, variable name list or dictionary where keys are Variable names, and the value can be a Mapping between variables and "pint" units, or a Dictionary with "name" (with the name of the variable in the files) and "unit" (with the "pint" unit name for this variable) keys.
        timestep : str | None, optional
            Timestep managed by the utils.TimestepEnum, by default None
        time_interval : str | None, optional
            Time interval in dd/mm/yyyy-dd/mm/yyyy or d/m/yyyy-d/m/yyyy, by default None
        radius_of_influence : int, optional
            Radius length in meters to use for resampling with nearest neighbours. Lower improves computation time but may result in less resulting data, by default 10000

        Returns
        -------
        xr.DataArray | xr.Dataset
            Resampled data, processed if requested (time alignment and time resampling).
        """
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
                dask_gufunc_kwargs={
                    "output_sizes": {
                        name: value
                        for name, value in var_dst_dims.items()
                        if name != "time"
                    }
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
