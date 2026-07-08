from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import cartopy.crs as ccrs
import numpy as np
import pandas as pd
import xarray as xr

from ClimateGraph.reader import Reader
from ClimateGraph.reader.reader.reader import ReadSpec
from ClimateGraph.utils.dataset_utils import (
    _record,
    change_unit,
    dim_reduction,
    normalize_vars,
)
from ClimateGraph.utils.general_utils import ReductionMethodEnum
from ClimateGraph.utils.registry import RegistryMixin
from ClimateGraph.utils.resample_engine import ResampleEngine, get_engine


class Data(RegistryMixin, ABC):
    """The Data abstract class.

    A class that abstracts the core nature of environmental data, independent of the topology of the data.
    This class contains and implements attributes and methods common to all the Data that ClimateGraph is supposed to handle.
    """

    registry: dict[str, type["Data"]] = {}
    aliases: list[str] = list()
    geom_dims: tuple[str, ...] = ()

    @classmethod
    def get_data_subclass(cls, name: str):
        return cls.get_class(name)

    @classmethod
    def check_topology_type(cls, type: str) -> bool:
        return cls.check_class(type)

    @classmethod
    def create(
        cls,
        name: str,
        topology: str,
        reader: str,
        path: Path | list[Path],
        vars: dict[str, dict[str, str]] | list[str] | None,
        crs: ccrs,
        reader_kwargs: dict,
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
        vars: dict[str, dict[str, str]] | list[str] | None,
        reader: Reader,
        crs: ccrs.CRS,
        reader_kwargs: dict[str, Any] | None = None,
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
        # Coerce list / None forms into the canonical dict-or-None shape so the
        # rest of Data (and the readers) only ever see a dict or None. Idempotent,
        # so copy() re-passing self.vars is safe.
        self._vars = normalize_vars(vars)
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
        if self._obj is None:
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
        self.resampled = None

    @property
    def geom(self):
        if self._geom is None:
            self._set_geom()
        return self._geom

    @property
    def vars(self):
        """vars Property getter method for getting the vars.

        Returns
        -------
        Dict[str, Dict[str, str]] | None
            Normalized dict mapping each user-facing variable name to a dict with
            "name" (file-native name) and "unit" (pint unit, possibly None)
            keys, or None when the data block declared no vars, and vars will be treated
            by native file names.
        """
        return self._vars

    def var_unit(self, var_name: str) -> str | None:
        """var_unit Resolve the declared source unit for ``var_name``.

        Single choke point for reading a variable's declared unit, so callers
        never index self.vars[...]["unit"]

        Parameters
        ----------
        var_name : str
            User-facing variable name.

        Returns
        -------
        str | None
            The declared pint unit, or ``None`` when vars wasn't declared.
        """
        if isinstance(self._vars, dict):
            entry = self._vars.get(var_name)
            if entry is not None:
                return entry.get("unit")
        return None

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
        """load_obj Load the actual data into the obj attribute by building
        a ReadSpec and invoking ``reader.read(spec)``. ``load_mode``,
        ``cache_dir`` and ``engine`` are pulled out of ``reader_kwargs``
        if present; the remainder lives on ``spec.extras`` for the
        subclass to consume.

        Returns
        -------
        xr.Dataset
            Xarray dataset of the Data object.
        """
        extras = dict(self.reader_kwargs)
        load_mode = extras.pop("load_mode", "safe")
        cache_dir = extras.pop("cache_dir", None)
        engine = extras.pop("engine", None)
        spec = ReadSpec(
            paths=self.path if isinstance(self.path, list) else [self.path],
            vars=self.vars,
            load_mode=load_mode,
            cache_dir=cache_dir,
            engine=engine,
            extras=extras,
        )
        self._obj = self.reader.read(spec)
        return self._obj

    # The var_name is the variable name not native to the file but as how it is referred in vars
    def get_var(
        self,
        var_name: str,
        in_unit: str | None = None,
        reduction_func: str | None = None,
        keep_dims: str | list[str] | None = None,
        reduction_dims: str | list[str] | None = None,
        as_array: bool = False,
        dim_reduce: dict[str, str | dict] | None = None,
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
        # After the reader runs the dataset is keyed by the user-facing names
        # (dict vars are renamed; list/None vars keep their file-native names,
        # which is what var_name already is), so var_name is the obj key.
        if var_name not in self.obj:
            raise KeyError(
                f"Variable {var_name!r} not found in dataset {self.name!r} "
                f"(available: {list(self.obj.data_vars)})."
            )
        xa = self.obj.data_vars[var_name]

        if dim_reduce is not None:
            xa = dim_reduction(xa, dim_reduce, name=var_name)

        if reduction_func is not None:
            reduction_func = (
                ReductionMethodEnum(reduction_func).func
                if isinstance(reduction_func, str)
                else reduction_func
            )
            if reduction_dims is None and keep_dims is not None:
                reduction_dims = list(set(self.dims) - set(keep_dims))
            xa = xa.reduce(reduction_func, reduction_dims)
            _record(
                xa,
                f"reduced {var_name!r} over {reduction_dims} with {reduction_func.__name__}",
            )

        if in_unit is not None:
            xa = change_unit(xa, self.var_unit(var_name), in_unit)

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
        missing_coords = [i for i in coord_names if i not in obj.coords]
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

    def resample_vars(
        self,
        other: "Data",
        vars: str | list[str],
        radius_of_influence: int = 10000,
        time_tolerance: str | None = "30min",
        engine: str | ResampleEngine = "pyresample",
        engine_kwargs: dict | None = None,
    ) -> xr.DataArray | xr.Dataset:
        """Project ``other``'s vars onto ``self``'s geometry (and time axis).

        A single responsibility: spatial resampling with the requested engine, plus
        a nearest-neighbour time *alignment* of ``other`` onto ``self``'s time axis.
        It does NOT convert units or filter/resample time — those belong to the
        caller (``get_var`` / the plot's ``change_unit`` and ``time_resampling``).

        Parameters
        ----------
        other : Data
            Other data object to resample into the "self" geometry.
        vars : str | list[str]
            Variable name or list of names to resample (kept in their source units).
        radius_of_influence : int, optional
            Radius length in meters to use for resampling. by default 10000
        time_tolerance : str | None, optional
            Pandas-style timedelta used as the tolerance when snapping ``other``'s
            time axis onto ``self``'s via nearest-neighbour reindex. Default ``"30min"``.
        engine : str | ResampleEngine, optional
            Resample backend name or instance. Default ``"pyresample"``.
        engine_kwargs : dict | None, optional
            Extra kwargs forwarded to the engine constructor
            (e.g. ``method``, ``sigmas``). Default None.

        Returns
        -------
        xr.DataArray | xr.Dataset
            Resampled data on ``self``'s geometry, aligned onto ``self``'s time axis.
        """
        if isinstance(vars, str):
            vars = [vars]

        resample_engine = get_engine(engine, **(engine_kwargs or {}))
        src_geom = other.geom
        dst_geom = self.geom

        info = resample_engine.prepare(
            src_geom,
            dst_geom,
            radius_of_influence=radius_of_influence,
        )
        _resample = resample_engine.make_resampler(info, dst_geom.shape)

        if self.resampled is None:
            self.resampled = self.obj.drop_vars(list(self.obj.data_vars))

        new_vars = []
        for var in vars:
            var_dst_dims = self.get_var(var).sizes
            var_src = other.get_var(var)

            if time_tolerance is not None and "time" in var_src.dims:
                var_src = var_src.reindex(
                    time=self.resampled["time"],
                    method="nearest",
                    tolerance=pd.Timedelta(time_tolerance),
                )

            src_geom_dims = [d for d in var_src.dims if d in set(other.geom_dims)]
            dst_geom_dims = [d for d in var_dst_dims if d in set(self.geom_dims)]
            resampled = xr.apply_ufunc(
                _resample,
                var_src,
                input_core_dims=[src_geom_dims],
                output_core_dims=[dst_geom_dims],
                vectorize=True,
                dask="parallelized",
                output_dtypes=[var_src.dtype],
                dask_gufunc_kwargs={
                    "output_sizes": {
                        name: value
                        for name, value in var_dst_dims.items()
                        if name in set(self.geom_dims)
                    }
                },
            )

            new_name = f"{var}__{other.name}"
            self.resampled[new_name] = resampled
            new_vars.append(new_name)

        _record(
            self.resampled,
            f"spatially resampled {new_vars} from {other.name} "
            f"({type(other).__name__}) to {self.name} ({type(self).__name__})",
        )

        save_to = self.reader_kwargs.get("save_resampled_to")
        if save_to:
            target = Path(save_to)
            target.parent.mkdir(parents=True, exist_ok=True)
            self.resampled.to_netcdf(target)
            _record(self.resampled, f"saved resampled data to {target}")

        return self.resampled[new_vars]
