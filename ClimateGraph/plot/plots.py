import math
from typing import Literal

import cartopy.feature as cfeature
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from pydantic import BaseModel, Field, model_validator

mpl.use("Agg")

from ClimateGraph.data import PointSurface, RegularGrid
from ClimateGraph.utils.dataset_utils import change_unit, time_resampling
from ClimateGraph.utils.general_utils import (
    CRSEnum,
    ReductionMethodEnum,
    TimeBucketEnum,
    TimestepEnum,
    manage_time_interval,
)

from .plot import Plot


def _drop_nan_points(
    lons: np.ndarray, lats: np.ndarray, vals: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """_drop_nan_points Drop the entries whose value is NaN, keeping the
    longitude / latitude / value arrays aligned. Used to strip empty stations
    from scatter overlays so they neither draw nor stretch the auto extent.
    """
    keep = ~np.isnan(vals)
    return lons[keep], lats[keep], vals[keep]


def _pad_extent(
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
    padding: float,
) -> tuple[float, float, float, float]:
    """_pad_extent Grow a (lon_min, lon_max, lat_min, lat_max) extent outward by
    ``padding`` (a fraction of each axis span) so auto-computed map bounds don't
    clip markers sitting on the edge. A zero-width span (e.g. a single point)
    falls back to a fixed 0.5-degree pad so ``set_extent`` stays valid.
    """
    lon_span = lon_max - lon_min
    lat_span = lat_max - lat_min
    lon_pad = lon_span * padding if lon_span else 0.5
    lat_pad = lat_span * padding if lat_span else 0.5
    return (
        lon_min - lon_pad,
        lon_max + lon_pad,
        lat_min - lat_pad,
        lat_max + lat_pad,
    )


class BasePlotConfig(BaseModel):
    """BasePlotConfig Base configuration as for all plots, Pydantic Model. Used to manage common arguments."""

    filename: str | None = Field(default=None)
    figsize: tuple[float, float] = Field((6, 6))
    format: str = Field(default="jpg")
    layout: Literal["constrained", "compressed", "tight", "none"] = Field(
        default="compressed"
    )
    dpi: int = Field(default=400)
    transparent: bool = Field(default=False)
    domains: list[str] = Field(default_factory=list)
    vars: str | list[str] | dict[str, str]


class TimeSeriesConfig(BasePlotConfig):
    """TimeSeriesConfig Timeseries plot configuration as Pydantic Model."""

    type: Literal["timeseries", "ts", "time-series"]
    base: str
    other_data: str | list[str] | None = Field(default=None)
    radius_of_influence: int | None = Field(default=None)
    time_interval: str | list[str] | None = Field(default=None)
    timestep: TimestepEnum | None = Field(default=None)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)
    colors: str | None = Field(default=None)  # TODO: implement


class Timeseries(Plot):
    """Timeseries plot class. Implements all particular operations for Timeseries plot creation."""

    config = TimeSeriesConfig
    aliases = ["ts", "time-series"]

    def plot(self):
        """plot Timeseries plotting method.
        The process goes as follows:
        1) Process arguments.
        2) Process base data: Time resampling and aligning, and unit conversion.
        3) Process other data: Space and Time resampling. Time alignment and unit conversion.
        4) Iterate through Domains and Vars.
            4.1) Apply domain to data objects.
            4.2) Reduce variable to time dimension.
            4.3) Plot variable for each data object.
        5) Save figure.
        """
        # TODO: remove time intervals with nan values.

        # Get relevant data from the config
        vars = self.plot_config.vars
        domains = {
            name: dom
            for name, dom in self.domains.items()
            if name in self.plot_config.domains
        }
        if not domains:
            domains = {"": None}

        radius_of_influence = self.plot_config.radius_of_influence
        timestep = self.plot_config.timestep
        time_interval = self.plot_config.time_interval

        base = self.data[self.plot_config.base]

        # Working on base data.
        # 1) Time resampling.
        # 2) Converting units if necessary.
        # 3) Renaming so it meets same standard as resampled data.

        base_obj = time_resampling(
            base.obj, timestep=timestep, time_interval=time_interval
        )
        for var in vars:
            if isinstance(vars, dict):
                base_obj[var] = change_unit(
                    base_obj[var], base.vars[var]["unit"], vars[var]
                )
        base_obj = base_obj.rename({name: name + "__" + base.name for name in vars})

        if self.plot_config.other_data is not None:
            if not isinstance(self.plot_config.other_data, list):
                self.plot_config.other_data = [self.plot_config.other_data]
            other_data = {
                name_: base.resample_vars(
                    data,
                    vars,
                    radius_of_influence=radius_of_influence,
                    timestep=timestep,
                    time_interval=time_interval,
                )
                for name_, data in {
                    name: self.data[name] for name in self.plot_config.other_data
                }.items()
            }
            other_data[self.plot_config.base] = base_obj
            all_data = other_data
        else:
            all_data = {self.plot_config.base: base_obj}

        # Plotting
        for dom_name, dom in domains.items():
            # Apply dom
            all_data_dom = (
                {name: dom.apply(data) for name, data in all_data.items()}
                if dom is not None
                else all_data
            )

            # Dimension reduction, TODO: make it so it can be other dim that gets plotted.
            all_data_dom = {
                name: data.reduce(
                    self.plot_config.reduction_method.func,
                    list(set(data.dims) - {"time"}),
                )
                for name, data in all_data_dom.items()
            }

            for variable in vars:
                unit = (
                    base.vars[variable]["unit"]
                    if not isinstance(vars, dict)
                    else vars[variable]
                )
                figure = plt.figure(
                    figsize=self.plot_kwargs.get("figsize", [6, 6]),
                    layout=self.plot_kwargs.get("layout", "constrained"),
                )
                ax = figure.add_subplot(1, 1, 1)

                for name, data_obj in all_data_dom.items():
                    obj_var = data_obj[f"{variable}__{name}"]
                    line = obj_var.plot.line(ax=ax)
                    line[0].set_label(name)

                ax.legend()

                title = self.plot_kwargs.get(
                    "title", f"Timeseries comparison of {variable}"
                )
                xlabel = self.plot_kwargs.get("xlabel", "Time")
                ylabel = self.plot_kwargs.get("ylabel", f"{variable} ({unit})")

                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)
                figure.suptitle(title)

                start, end = manage_time_interval(time_interval)
                format = self.plot_kwargs.get("format", "jpg")
                filename = (
                    f"ts-{dom_name}-{variable}-{start.strftime('%d-%m-%Y')}_{end.strftime('%d-%m-%Y')}.{format}"
                    if self.plot_config.filename is None
                    else self.plot_config.filename
                )

                self.savefig(figure, filename)


class ScatterConfig(BasePlotConfig):
    """ScatterConfig Scatter plot configuration Pydantic model."""

    type: Literal["scatter", "sc"]
    base: str
    other: str
    radius_of_influence: int
    time_interval: str
    dimension: str = Field(default="time")
    timestep: TimestepEnum | None = Field(default=None)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)
    colors: str | None = Field(default=None)  # TODO: implement


class Scatter(Plot):
    """Scatter plot class. Implements all particular operations for scatter plot creation.

    Parameters
    ----------
    Plot : _type_
        _description_
    """

    config = ScatterConfig
    aliases = ["sc"]

    def plot(self):
        """plot Scatter plotting method.
        The process goes as follows:
        1) Process arguments.
        2) Process base data: Time resampling and aligning, and unit conversion.
        3) Process other data: Space and Time resampling. Time alignment and unit conversion.
        4) Iterate through Domains.
            4.1) Apply domain to data objects.
            4.2) Reduce variable to desired dimension.
            4.3) Iterate through Variables
                4.3.1) Scatter plot from "base" and "other" variable
            4.4) Save figure.
        """
        # Get relevant data from the config
        base = self.data[self.plot_config.base]
        other = self.data[self.plot_config.other]
        vars = self.plot_config.vars
        radius_of_influence = self.plot_config.radius_of_influence
        timestep = self.plot_config.timestep
        time_interval = self.plot_config.time_interval
        domains = {
            name: dom
            for name, dom in self.domains.items()
            if name in self.plot_config.domains
        }
        if not domains:
            domains = {"": None}

        # Managing base data:
        # 1) Time resampling and alignment
        # 2) Change measure units accordingly

        base_obj = time_resampling(
            base.obj, timestep=timestep, time_interval=time_interval
        )
        for var in vars:
            unit = base.vars[var]["unit"] if isinstance(vars, list | str) else vars[var]
            base_obj[var] = change_unit(
                base_obj[var], base.vars[var]["unit"], vars[var]
            )

        base_obj = base_obj.rename({name: name + "__" + base.name for name in vars})

        # Managing other data:
        # 1) Space and time resampling. Time alignment.

        other_obj = base.resample_vars(
            other,
            vars,
            radius_of_influence=radius_of_influence,
            timestep=timestep,
            time_interval=time_interval,
        )

        for dom_name, dom in domains.items():
            # Plotting

            # Filtering with domain
            if dom is not None:
                base_obj_dom = dom.apply(base_obj)
                other_obj_dom = dom.apply(other_obj)
            else:
                base_obj_dom = base_obj
                other_obj_dom = other_obj

            # Reducing dimensionality
            base_obj_dom = base_obj_dom.reduce(
                self.plot_config.reduction_method.func,
                list(set(base_obj_dom.dims) - {self.plot_config.dimension}),
            )
            other_obj_dom = other_obj_dom.reduce(
                self.plot_config.reduction_method.func,
                list(set(other_obj_dom.dims) - {self.plot_config.dimension}),
            )

            for variable, unit in vars.items():
                unit = (
                    base.vars[variable]["unit"]
                    if isinstance(vars, list | str)
                    else vars[variable]
                )
                figure = plt.figure(
                    figsize=self.plot_kwargs.get("figsize", [6, 6]),
                    layout=self.plot_kwargs.get("layout", "constrained"),
                )
                base_var, other_var = (
                    base_obj_dom[f"{variable}__{base.name}"],
                    other_obj_dom[f"{variable}__{other.name}"],
                )
                ax = figure.add_subplot(1, 1, 1)
                min_val, max_val = (
                    math.floor(np.nanmin([np.nanmin(base_var), np.nanmin(other_var)])),
                    math.ceil(np.nanmax([np.nanmax(base_var), np.nanmax(other_var)])),
                )

                title = self.plot_kwargs.get(
                    "title",
                    f"Scatter comparison of {variable} between {base.name} and {other.name}",
                )
                xlabel = self.plot_kwargs.get(
                    "xlabel", f"{variable} [{unit}], {base.name}"
                )
                ylabel = self.plot_kwargs.get(
                    "ylabel", f"{variable} [{unit}], {other.name}"
                )

                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)

                figure.suptitle(title)
                ax.set_xlim(min_val, max_val)
                ax.set_ylim(min_val, max_val)

                ax.scatter(base_var.values, other_var.values)

                x = [min_val + x * (max_val - min_val) / 5 for x in range(5 + 1)]
                ax.plot(x, x)

                start, end = manage_time_interval(time_interval)
                format = self.plot_kwargs.get("format", "jpg")
                filename = (
                    f"scatter-{dom_name}-{variable}-{start.strftime('%d-%m-%Y')}_{end.strftime('%d-%m-%Y')}.{format}"
                    if self.plot_config.filename is None
                    else self.plot_config.filename
                )
                self.savefig(figure, filename)


class SpatialOverlayConfig(BasePlotConfig):
    """SpatialOverlay Spatial-Overlay plot configuration Pydantic model."""

    type: Literal["spatial-overlay", "spatialoverlay", "so"]
    base: str
    superposed: str
    time_interval: str
    levels: int = Field(default=10)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)
    crs: CRSEnum | None = Field(default=None)
    coastlines: bool = Field(default=True)
    borders: bool = Field(default=True)
    cmap: str = Field(default="viridis")
    bbox: list[float | int] = Field(default=None)
    padding: float = Field(default=0.05)
    drop_nans: bool = Field(default=False)


class SpatialOverlay(Plot):
    """SpatialOverlay plot class. Implements all particular operations for spatial-overlay plot creation."""

    aliases = ["spatial-overlay", "spatialoverlay", "so"]
    config = SpatialOverlayConfig

    def plot(self):
        """plot Spatial Overlay plotting method.
        The process goes as follows:
        1) Process arguments.
        2) Iterate through Domains.
            2.1) Apply domains to data objects.
            2.2) Time alignment.
            2.3) Reduce variable to latitude and longitude.
            2.4) Iterate through Variables
                2.4.1) Contourf spatially distributed data variable plot from "base".
                2.4.2) Scatter point surface data variable plot from "superposed".
                2.4.3) Save figure.
        """
        # Get relevant data from the config
        base: RegularGrid = self.data[self.plot_config.base]
        superposed: PointSurface = self.data[self.plot_config.superposed]
        vars = self.plot_config.vars
        time_interval = self.plot_config.time_interval
        crs = (
            base.crs.crs if self.plot_config.crs is None else self.plot_config.crs.crs
        )  # TODO: make this simpler haha
        domains = {
            name: dom
            for name, dom in self.domains.items()
            if name in self.plot_config.domains
        }
        if not domains:
            domains = {"": None}

        for dom_name, dom in domains.items():
            for var in vars:
                base_var = base.obj[var]
                superposed_var = superposed.obj[var]
                if dom is not None:
                    base_var = dom.apply(base_var)
                    superposed_var = dom.apply(superposed_var)

                unit = (
                    base.vars[var]["unit"]
                    if isinstance(vars, list | str)
                    else vars[var]
                )

                # Time alignment
                base_var = time_resampling(base_var, time_interval=time_interval)
                superposed_var = time_resampling(
                    superposed_var, time_interval=time_interval
                )

                # Reduction
                base_reduction_dims = [x for x in ["time", "z"] if x in base.dims]
                base_var = base_var.reduce(
                    self.plot_config.reduction_method.func, base_reduction_dims
                )
                superposed_var = superposed_var.reduce(
                    self.plot_config.reduction_method.func, "time"
                )

                # unit conversion
                base_var = change_unit(base_var, base.vars[var]["unit"], unit)
                superposed_var = change_unit(
                    superposed_var, superposed.vars[var]["unit"], unit
                )

                # Plotting
                figure = plt.figure(
                    figsize=self.plot_kwargs.get("figsize", [6, 6]),
                    layout=self.plot_kwargs.get("layout", "constrained"),
                )

                ax = figure.add_subplot(1, 1, 1, projection=crs())

                if self.plot_config.coastlines:
                    ax.coastlines()
                if self.plot_config.borders:
                    ax.add_feature(cfeature.BORDERS)

                figure.suptitle(
                    f"Spatial overlay comparison of {var} between {base.name} and {superposed.name}"
                )

                vmin, vmax = (
                    np.nanmin([base_var.min(), superposed_var.min()]),
                    np.nanmax([base_var.max(), superposed_var.max()]),
                )

                # Superposed (point) coords/values, optionally dropping the
                # stations whose reduced observation is NaN so empty sites
                # neither draw nor stretch the auto extent.
                sup_lons = superposed_var["longitude"].values
                sup_lats = superposed_var["latitude"].values
                sup_vals = superposed_var.values
                if self.plot_config.drop_nans:
                    sup_lons, sup_lats, sup_vals = _drop_nan_points(
                        sup_lons, sup_lats, sup_vals
                    )

                if self.plot_config.bbox is not None:
                    lon_min, lat_min, lon_max, lat_max = self.plot_config.bbox
                else:
                    lon_min = np.nanmax(
                        [np.nanmin(base_var["longitude"]), np.nanmin(sup_lons)]
                    )
                    lat_min = np.nanmax(
                        [np.nanmin(base_var["latitude"]), np.nanmin(sup_lats)]
                    )
                    lon_max = np.nanmin(
                        [np.nanmax(base_var["longitude"]), np.nanmax(sup_lons)]
                    )
                    lat_max = np.nanmin(
                        [np.nanmax(base_var["latitude"]), np.nanmax(sup_lats)]
                    )
                    lon_min, lon_max, lat_min, lat_max = _pad_extent(
                        lon_min, lon_max, lat_min, lat_max, self.plot_config.padding
                    )

                norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)

                ax.contourf(
                    base_var["longitude"].values,
                    base_var["latitude"].values,
                    base_var.values,
                    transform=base.crs.crs(),
                    cmap=self.plot_config.cmap,
                    norm=norm,
                    levels=self.plot_config.levels,
                )

                ax.scatter(
                    sup_lons,
                    sup_lats,
                    c=sup_vals,
                    transform=superposed.crs.crs(),
                    cmap=self.plot_config.cmap,
                    norm=norm,
                    edgecolor="k",
                )

                ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=crs())

                sm = mpl.cm.ScalarMappable(norm=norm, cmap=self.plot_config.cmap)

                figure.colorbar(
                    sm, ax=ax, orientation="vertical", label=f"{var} [{unit}]"
                )

                start, end = manage_time_interval(time_interval)
                format = self.plot_kwargs.get("format", "jpg")
                filename = (
                    f"spatial_overlay-{dom_name}-{var}-{base.name}-{superposed.name}-{start.strftime('%d-%m-%Y')}_{end.strftime('%d-%m-%Y')}.{format}"
                    if self.plot_config.filename is None
                    else self.plot_config.filename
                )

                self.savefig(figure, filename)


class SpatialMapConfig(BasePlotConfig):
    """SpatialMap single-dataset map plot configuration Pydantic model."""

    type: Literal["spatial-map", "spatialmap", "map", "sm"]
    data: str
    time_interval: str
    levels: int = Field(default=10)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)
    crs: CRSEnum | None = Field(default=None)
    coastlines: bool = Field(default=True)
    borders: bool = Field(default=True)
    cmap: str = Field(default="viridis")
    bbox: list[float | int] | None = Field(default=None)
    markersize: float = Field(default=40.0)
    padding: float = Field(default=0.05)
    drop_nans: bool = Field(default=False)


class SpatialMap(Plot):
    """SpatialMap plot class. Plots a single dataset over a map.

    The rendering style is chosen from the dataset topology: spatially
    distributed data (``RegularGrid``) is drawn as a filled contour
    (``contourf``); in-situ data (``PointSurface`` and any other topology)
    is drawn as a coloured ``scatter`` of points. It is, in essence, one
    half of ``SpatialOverlay`` applied to a single dataset.
    """

    aliases = ["spatial-map", "spatialmap", "map", "sm"]
    config = SpatialMapConfig

    def plot(self):
        """plot Spatial Map plotting method.
        The process goes as follows:
        1) Process arguments.
        2) Iterate through Domains.
            2.1) Apply domain to the data object.
            2.2) Time alignment.
            2.3) Reduce variable to latitude and longitude.
            2.4) Iterate through Variables
                2.4.1) Contourf for RegularGrid data, scatter otherwise.
                2.4.2) Save figure.
        """
        # Get relevant data from the config
        data: RegularGrid | PointSurface = self.data[self.plot_config.data]
        vars = self.plot_config.vars
        time_interval = self.plot_config.time_interval
        crs = data.crs.crs if self.plot_config.crs is None else self.plot_config.crs.crs
        domains = {
            name: dom
            for name, dom in self.domains.items()
            if name in self.plot_config.domains
        }
        if not domains:
            domains = {"": None}

        # RegularGrid renders as a filled contour, everything else as points.
        is_grid = isinstance(data, RegularGrid)

        for dom_name, dom in domains.items():
            for var in vars:
                data_var = data.obj[var]
                if dom is not None:
                    data_var = dom.apply(data_var)

                unit = (
                    data.vars[var]["unit"]
                    if isinstance(vars, list | str)
                    else vars[var]
                )

                # Time alignment
                data_var = time_resampling(data_var, time_interval=time_interval)

                # Reduction down to the spatial dims (latitude, longitude).
                reduction_dims = [x for x in ["time", "z"] if x in data.dims]
                data_var = data_var.reduce(
                    self.plot_config.reduction_method.func, reduction_dims
                )

                # Unit conversion
                data_var = change_unit(data_var, data.vars[var]["unit"], unit)

                # Plotting
                figure = plt.figure(
                    figsize=self.plot_kwargs.get("figsize", [6, 6]),
                    layout=self.plot_kwargs.get("layout", "constrained"),
                )

                ax = figure.add_subplot(1, 1, 1, projection=crs())

                if self.plot_config.coastlines:
                    ax.coastlines()
                if self.plot_config.borders:
                    ax.add_feature(cfeature.BORDERS)

                figure.suptitle(
                    self.plot_kwargs.get(
                        "title", f"Spatial map of {var} for {data.name}"
                    )
                )

                vmin, vmax = np.nanmin(data_var), np.nanmax(data_var)
                norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)

                lons = data_var["longitude"].values
                lats = data_var["latitude"].values

                if is_grid:
                    ax.contourf(
                        lons,
                        lats,
                        data_var.values,
                        transform=data.crs.crs(),
                        cmap=self.plot_config.cmap,
                        norm=norm,
                        levels=self.plot_config.levels,
                    )
                else:
                    vals = data_var.values
                    # Drop stations whose reduced observation is NaN so empty
                    # sites neither draw nor stretch the auto extent.
                    if self.plot_config.drop_nans:
                        lons, lats, vals = _drop_nan_points(lons, lats, vals)
                    ax.scatter(
                        lons,
                        lats,
                        c=vals,
                        s=self.plot_config.markersize,
                        transform=data.crs.crs(),
                        cmap=self.plot_config.cmap,
                        norm=norm,
                        edgecolor="k",
                    )

                if self.plot_config.bbox is not None:
                    lon_min, lat_min, lon_max, lat_max = self.plot_config.bbox
                else:
                    lon_min, lon_max = np.nanmin(lons), np.nanmax(lons)
                    lat_min, lat_max = np.nanmin(lats), np.nanmax(lats)
                    lon_min, lon_max, lat_min, lat_max = _pad_extent(
                        lon_min, lon_max, lat_min, lat_max, self.plot_config.padding
                    )

                ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=crs())

                sm = mpl.cm.ScalarMappable(norm=norm, cmap=self.plot_config.cmap)
                figure.colorbar(
                    sm, ax=ax, orientation="vertical", label=f"{var} [{unit}]"
                )

                start, end = manage_time_interval(time_interval)
                format = self.plot_kwargs.get("format", "jpg")
                filename = (
                    f"spatial_map-{dom_name}-{var}-{data.name}-{start.strftime('%d-%m-%Y')}_{end.strftime('%d-%m-%Y')}.{format}"
                    if self.plot_config.filename is None
                    else self.plot_config.filename
                )

                self.savefig(figure, filename)


class TimeCycleConfig(BasePlotConfig):
    """TimeSeriesConfig Timeseries plot configuration as Pydantic Model."""

    type: Literal["timecycle", "time cycle", "cycle"]
    base: str
    other_data: str | list[str] | None = Field(default=None)
    radius_of_influence: int | None = Field(default=None)
    time_interval: str | list[str] | None = Field(default=None)
    timestep: TimestepEnum | None = Field(default=None)
    time_buckets: TimeBucketEnum = Field(default=TimeBucketEnum.day)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)

    @model_validator(mode="after")
    def check_timestep_vs_bucket(self) -> "TimeCycleConfig":
        if self.timestep is None:
            return self
        # map both to hours for comparison
        bucket_hours = {
            "hour": 1,
            "day": 24,
            "month": 720,
            "dayofyear": 24,
            "season": 2160,
        }
        timestep_hours = {
            TimestepEnum.hourly: 1,
            TimestepEnum.daily: 24,
            TimestepEnum.monthly: 720,
            # extend as needed
        }
        if timestep_hours[self.timestep] > bucket_hours[self.time_buckets.value]:
            raise ValueError(
                f"timestep '{self.timestep}' is coarser than "
                f"time_bucket '{self.time_buckets.value}' — std bands will be meaningless"
            )
        return self


class TimeCycle(Plot):
    config = TimeCycleConfig
    aliases = ["time cycle", "cycle"]

    def plot(self):
        # Get relevant data from the config
        vars = self.plot_config.vars
        domains = {
            name: dom
            for name, dom in self.domains.items()
            if name in self.plot_config.domains
        }
        if not domains:
            domains = {"": None}

        radius_of_influence = self.plot_config.radius_of_influence
        time_interval = self.plot_config.time_interval
        timestep = self.plot_config.timestep
        time_bucket = (
            self.plot_config.time_buckets.value
        )  # e.g. "hour", "month", "dayofyear"

        base = self.data[self.plot_config.base]
        # Base data: time interval filter and unit conversion, no timestep resampling
        # (groupby needs the original time resolution intact)
        base_obj = time_resampling(base.obj, timestep=None, time_interval=time_interval)
        for var in vars:
            if isinstance(vars, dict):
                base_obj[var] = change_unit(
                    base_obj[var], base.vars[var]["unit"], vars[var]
                )
        base_obj = base_obj.rename({name: name + "__" + base.name for name in vars})

        # Other data: spatial resampling + time interval, but no timestep resampling
        if self.plot_config.other_data is not None:
            if not isinstance(self.plot_config.other_data, list):
                self.plot_config.other_data = [self.plot_config.other_data]
            other_data = {
                name_: base.resample_vars(
                    data,
                    vars,
                    radius_of_influence=radius_of_influence,
                    timestep=timestep,
                    time_interval=time_interval,
                )
                for name_, data in {
                    name: self.data[name] for name in self.plot_config.other_data
                }.items()
            }
            other_data[self.plot_config.base] = base_obj
            all_data = other_data
        else:
            all_data = {self.plot_config.base: base_obj}

        # Plotting
        for dom_name, dom in domains.items():
            # Apply domain
            all_data_dom = (
                {name: dom.apply(data) for name, data in all_data.items()}
                if dom is not None
                else all_data
            )

            # Reduce all non-time spatial dims before groupby
            all_data_dom = {
                name: data.reduce(
                    self.plot_config.reduction_method.func,
                    list(set(data.dims) - {"time"}),
                )
                for name, data in all_data_dom.items()
            }

            for variable in vars:
                unit = (
                    base.vars[variable]["unit"]
                    if not isinstance(vars, dict)
                    else vars[variable]
                )

                figure = plt.figure(
                    figsize=self.plot_kwargs.get("figsize", [8, 5]),
                    layout=self.plot_kwargs.get("layout", "constrained"),
                )
                ax = figure.add_subplot(1, 1, 1)

                xticklabels = None

                for name, data_obj in all_data_dom.items():
                    da = data_obj[f"{variable}__{name}"]

                    grouped = da.groupby(f"time.{time_bucket}")
                    mean = grouped.mean("time", skipna=True)
                    std = grouped.std("time", skipna=True)

                    bucket_vals = mean[time_bucket].values
                    xticklabels = (
                        xticklabels if xticklabels is not None else bucket_vals
                    )

                    ax.plot(bucket_vals, mean.values, label=name)
                    ax.fill_between(
                        bucket_vals, (mean - std).values, (mean + std).values, alpha=0.2
                    )

                title = self.plot_kwargs.get("title", f"Diurnal cycle of {variable}")
                xlabel = self.plot_kwargs.get("xlabel", time_bucket.capitalize())
                ylabel = self.plot_kwargs.get("ylabel", f"{variable} ({unit})")

                ax.set_xlabel(xlabel)
                ax.set_xticks(list(range(len(xticklabels))))
                ax.set_xticklabels(xticklabels)
                ax.set_ylabel(ylabel)
                ax.legend()
                figure.suptitle(title)

                start, end = manage_time_interval(time_interval)
                fmt = self.plot_kwargs.get("format", "jpg")
                filename = (
                    f"cycle-{time_bucket}-{dom_name}-{variable}"
                    f"-{start.strftime('%d-%m-%Y')}_{end.strftime('%d-%m-%Y')}.{fmt}"
                    if self.plot_config.filename is None
                    else self.plot_config.filename
                )

                self.savefig(figure, filename)
