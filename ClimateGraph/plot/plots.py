import math
from typing import Literal

import cartopy.feature as cfeature
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

mpl.use("Agg")

from ClimateGraph.data import PointSurface, RegularGrid
from ClimateGraph.utils.dataset_utils import change_unit, dim_reduction, time_resampling
from ClimateGraph.utils.general_utils import (
    CRSEnum,
    ReductionMethodEnum,
    TimeBucketEnum,
    TimestepEnum,
    manage_time_interval,
    normalize_time,
)

from . import primitives as _primitives  # noqa: F401  registers primitive configs
from .plot import Plot
from .primitive import Primitive

# Discriminated union over the registered primitive configs (Series/ContourFill/
# Points). Built here — after importing `primitives` — so every primitive config
# is registered before CustomPlotConfig references it.
PrimitiveModel = Primitive.build_config_union()


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


def _unit_label(name: str, unit: str | None) -> str:
    """_unit_label Format an axis/colorbar label as ``name [unit]``.

    Single style for every plot (square brackets), and omits the unit entirely
    when it's unknown (``None``) so labels never read ``"Temperatura [None]"``.
    """
    return f"{name} [{unit}]" if unit else name


class BasePlotConfig(BaseModel):
    """BasePlotConfig Base configuration as for all plots, Pydantic Model. Used to manage common arguments."""

    model_config = ConfigDict(extra="allow")

    filename: str | None = Field(default=None)
    domains: list[str] = Field(default_factory=list)
    vars: list[str] | dict[str, str]
    dim_reduce: dict[str, str | dict] | None = Field(default=None)

    @field_validator("vars", mode="before")
    @classmethod
    def _wrap_single_var(cls, v):
        """Coerce a lone ``vars: T2`` string into ``["T2"]`` so plot methods
        iterate over variable names, not the characters of a single name."""
        if isinstance(v, str):
            return [v]
        return v


class TimeSeriesConfig(BasePlotConfig):
    """TimeSeriesConfig Timeseries plot configuration as Pydantic Model."""

    type: Literal["timeseries", "ts", "time-series"]
    data: str | list[str]
    time: str | list[str] | None = Field(default=None)
    timestep: TimestepEnum | None = Field(default=None)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)
    colors: str | None = Field(default=None)  # TODO: implement

    @field_validator("data", mode="before")
    @classmethod
    def _wrap_single_data(cls, v):
        return [v] if isinstance(v, str) else v


class Timeseries(Plot):
    """Timeseries plot class. Implements all particular operations for Timeseries plot creation."""

    config = TimeSeriesConfig
    aliases = ["ts", "time-series"]

    def plot(self):
        """plot Iterate over self.plot_config.time entries, rendering once per entry."""
        for time_interval in normalize_time(self.plot_config.time):
            self._plot_one(time_interval)

    def _plot_one(self, time_interval: str | None):
        """_plot_one Timeseries plotting method for a single time entry.
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

        vars = self.plot_config.vars
        domains = self.resolve_domains()
        timestep = self.plot_config.timestep
        data_names = self.plot_config.data
        first = self.data[data_names[0]]

        for dom_name, dom in domains.items():
            # Apply the domain to each raw Data object (Data -> Data; resample
            # domains reproject here), then time-filter. Canonical var names — no
            # {var}__{dataset} mangling; each dataset is handled on its own.
            prepared = {}
            for ds_name in data_names:
                d = self.data[ds_name]
                d = dom.apply(d) if dom is not None else d
                obj = time_resampling(
                    d.obj, timestep=timestep, time_interval=time_interval
                )
                prepared[ds_name] = (d, obj)

            for variable in vars:
                # dict vars -> convert to the requested unit; list vars -> keep
                # native (dst None) and label with the first dataset's declared unit.
                dst_unit = vars[variable] if isinstance(vars, dict) else None
                label_unit = (
                    vars[variable]
                    if isinstance(vars, dict)
                    else first.var_unit(variable)
                )

                figure = plt.figure(**self.figure_kwargs())
                ax = figure.add_subplot(1, 1, 1)

                for ds_name, (d, obj) in prepared.items():
                    da = obj[variable]
                    if self.plot_config.dim_reduce:
                        da = dim_reduction(da, self.plot_config.dim_reduce)
                    da = da.reduce(
                        self.plot_config.reduction_method.func,
                        list(set(da.dims) - {"time"}),
                    )
                    da = change_unit(da, d.var_unit(variable), dst_unit)
                    line = da.plot.line(ax=ax)
                    line[0].set_label(ds_name)

                ax.legend()

                title = self.plot_kwargs.get(
                    "title", f"Timeseries comparison of {variable}"
                )
                xlabel = self.plot_kwargs.get("xlabel", "Time")
                ylabel = self.plot_kwargs.get(
                    "ylabel", _unit_label(variable, label_unit)
                )

                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)
                figure.suptitle(title)

                start, end = manage_time_interval(time_interval)
                start = "start" if start is None else start.strftime("%d-%m-%Y")
                end = "end" if end is None else end.strftime("%d-%m-%Y")
                format = self.plot_kwargs.get("format", "jpg")
                filename = (
                    f"ts-{dom_name}-{variable}-{start}_{end}.{format}"
                    if self.plot_config.filename is None
                    else self.plot_config.filename
                )

                self.savefig(figure, filename)


class ScatterConfig(BasePlotConfig):
    """ScatterConfig Scatter plot configuration Pydantic model."""

    type: Literal["scatter", "sc"]
    # Exactly two datasets — [x-axis, y-axis]. Co-location (pairing per site)
    # is expressed with a `resample_to` domain; pairing per time needs none.
    data: list[str]
    time: str | list[str] | None = Field(default=None)
    dimension: str = Field(default="time")
    timestep: TimestepEnum | None = Field(default=None)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)
    colors: str | None = Field(default=None)  # TODO: implement

    @field_validator("data")
    @classmethod
    def _exactly_two(cls, v):
        if len(v) != 2:
            raise ValueError(
                "scatter 'data' must list exactly two datasets: [x-axis, y-axis]."
            )
        return v


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
        """plot Iterate over self.plot_config.time entries, rendering once per entry."""
        for time_interval in normalize_time(self.plot_config.time):
            self._plot_one(time_interval)

    def _plot_one(self, time_interval: str | None):
        """_plot_one Scatter plotting method for a single time entry.

        Pairs two datasets value-for-value: ``data[0]`` on x, ``data[1]`` on y.
        Per domain, each dataset gets the domain applied as a RAW Data object (a
        resample_to domain co-locates them here), is time-filtered, then reduced
        over every dim except ``dimension`` so the two align for pairing.
        """
        vars = self.plot_config.vars
        timestep = self.plot_config.timestep
        dimension = self.plot_config.dimension
        domains = self.resolve_domains()
        x_name, y_name = self.plot_config.data

        for dom_name, dom in domains.items():
            prepared = {}
            for ds_name in (x_name, y_name):
                d = self.data[ds_name]
                d = dom.apply(d) if dom is not None else d
                obj = time_resampling(
                    d.obj, timestep=timestep, time_interval=time_interval
                )
                prepared[ds_name] = (d, obj)

            for variable in vars:
                unit = vars[variable] if isinstance(vars, dict) else None
                reduced = {}
                for ds_name, (d, obj) in prepared.items():
                    da = obj[variable]
                    if self.plot_config.dim_reduce:
                        da = dim_reduction(da, self.plot_config.dim_reduce)
                    da = da.reduce(
                        self.plot_config.reduction_method.func,
                        list(set(da.dims) - {dimension}),
                    )
                    da = change_unit(da, d.var_unit(variable), unit)
                    reduced[ds_name] = da

                x_var, y_var = reduced[x_name], reduced[y_name]
                figure = plt.figure(**self.figure_kwargs())
                ax = figure.add_subplot(1, 1, 1)
                min_val, max_val = (
                    math.floor(np.nanmin([np.nanmin(x_var), np.nanmin(y_var)])),
                    math.ceil(np.nanmax([np.nanmax(x_var), np.nanmax(y_var)])),
                )

                title = self.plot_kwargs.get(
                    "title",
                    f"Scatter comparison of {variable} between {x_name} and {y_name}",
                )
                xlabel = self.plot_kwargs.get(
                    "xlabel", f"{_unit_label(variable, unit)}, {x_name}"
                )
                ylabel = self.plot_kwargs.get(
                    "ylabel", f"{_unit_label(variable, unit)}, {y_name}"
                )

                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)

                figure.suptitle(title)
                ax.set_xlim(min_val, max_val)
                ax.set_ylim(min_val, max_val)

                ax.scatter(x_var.values, y_var.values)

                x = [min_val + x * (max_val - min_val) / 5 for x in range(5 + 1)]
                ax.plot(x, x)

                start, end = manage_time_interval(time_interval)
                start = "start" if start is None else start.strftime("%d-%m-%Y")
                end = "end" if end is None else end.strftime("%d-%m-%Y")
                format = self.plot_kwargs.get("format", "jpg")
                filename = (
                    f"scatter-{dom_name}-{variable}-{start}_{end}.{format}"
                    if self.plot_config.filename is None
                    else self.plot_config.filename
                )
                self.savefig(figure, filename)


class SpatialOverlayConfig(BasePlotConfig):
    """SpatialOverlay Spatial-Overlay plot configuration Pydantic model."""

    type: Literal["spatial-overlay", "spatialoverlay", "so"]
    base: str
    superposed: str
    time: str | list[str] | None = Field(default=None)
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
        """plot Iterate over self.plot_config.time entries, rendering once per entry."""
        for time_interval in normalize_time(self.plot_config.time):
            self._plot_one(time_interval)

    def _plot_one(self, time_interval: str | None):
        """_plot_one Spatial Overlay plotting method for a single time entry.
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
            base_dom = dom.apply(base) if dom is not None else base
            superposed_dom = dom.apply(superposed) if dom is not None else superposed
            for var in vars:
                base_var = base_dom.obj[var]
                superposed_var = superposed_dom.obj[var]

                unit = base.var_unit(var) if isinstance(vars, list | str) else vars[var]

                # Time alignment
                base_var = time_resampling(base_var, time_interval=time_interval)
                superposed_var = time_resampling(
                    superposed_var, time_interval=time_interval
                )

                if self.plot_config.dim_reduce:
                    base_var = dim_reduction(base_var, self.plot_config.dim_reduce)
                    superposed_var = dim_reduction(
                        superposed_var, self.plot_config.dim_reduce
                    )

                base_reduction_dims = [x for x in ["time", "z"] if x in base_var.dims]
                base_var = base_var.reduce(
                    self.plot_config.reduction_method.func, base_reduction_dims
                )
                superposed_var = superposed_var.reduce(
                    self.plot_config.reduction_method.func, "time"
                )

                # unit conversion
                base_var = change_unit(base_var, base.var_unit(var), unit)
                superposed_var = change_unit(
                    superposed_var, superposed.var_unit(var), unit
                )

                # Plotting
                figure = plt.figure(**self.figure_kwargs())

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
                    sm, ax=ax, orientation="vertical", label=_unit_label(var, unit)
                )

                start, end = manage_time_interval(time_interval)
                start = "start" if start is None else start.strftime("%d-%m-%Y")
                end = "end" if end is None else end.strftime("%d-%m-%Y")
                format = self.plot_kwargs.get("format", "jpg")
                filename = (
                    f"spatial_overlay-{dom_name}-{var}-{base.name}-{superposed.name}-{start}_{end}.{format}"
                    if self.plot_config.filename is None
                    else self.plot_config.filename
                )

                self.savefig(figure, filename)


class SpatialMapConfig(BasePlotConfig):
    """SpatialMap single-dataset map plot configuration Pydantic model."""

    type: Literal["spatial-map", "spatialmap", "map", "sm"]
    data: str
    time: str | list[str] | None = Field(default=None)
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
        """plot Iterate over self.plot_config.time entries, rendering once per entry."""
        for time_interval in normalize_time(self.plot_config.time):
            self._plot_one(time_interval)

    def _plot_one(self, time_interval: str | None):
        """_plot_one Spatial Map plotting method for a single time entry.
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
            data_dom = dom.apply(data) if dom is not None else data
            for var in vars:
                data_var = data_dom.obj[var]

                unit = data.var_unit(var) if isinstance(vars, list | str) else vars[var]

                # Time alignment
                data_var = time_resampling(data_var, time_interval=time_interval)

                if self.plot_config.dim_reduce:
                    data_var = dim_reduction(data_var, self.plot_config.dim_reduce)

                reduction_dims = [x for x in ["time", "z"] if x in data_var.dims]
                data_var = data_var.reduce(
                    self.plot_config.reduction_method.func, reduction_dims
                )

                # Unit conversion
                data_var = change_unit(data_var, data.var_unit(var), unit)

                # Plotting
                figure = plt.figure(**self.figure_kwargs())

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
                    sm, ax=ax, orientation="vertical", label=_unit_label(var, unit)
                )

                start, end = manage_time_interval(time_interval)
                start = "start" if start is None else start.strftime("%d-%m-%Y")
                end = "end" if end is None else end.strftime("%d-%m-%Y")
                format = self.plot_kwargs.get("format", "jpg")
                filename = (
                    f"spatial_map-{dom_name}-{var}-{data.name}-{start}_{end}.{format}"
                    if self.plot_config.filename is None
                    else self.plot_config.filename
                )

                self.savefig(figure, filename)


class TimeCycleConfig(BasePlotConfig):
    """TimeCycleConfig TimeCycle plot configuration as Pydantic Model."""

    type: Literal["timecycle", "time cycle", "cycle"]
    # One or more datasets; the first is the reference and gets the ± std band.
    data: str | list[str]
    time: str | list[str] | None = Field(default=None)
    timestep: TimestepEnum | None = Field(default=None)
    time_buckets: TimeBucketEnum = Field(default=TimeBucketEnum.day)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)

    @field_validator("data", mode="before")
    @classmethod
    def _wrap_single_data(cls, v):
        return [v] if isinstance(v, str) else v

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
        """plot Iterate over self.plot_config.time entries, rendering once per entry."""
        for time_interval in normalize_time(self.plot_config.time):
            self._plot_one(time_interval)

    def _plot_one(self, time_interval: str | None):
        vars = self.plot_config.vars
        domains = self.resolve_domains()
        timestep = self.plot_config.timestep
        time_bucket = (
            self.plot_config.time_buckets.value
        )  # e.g. "hour", "month", "dayofyear"
        data_names = self.plot_config.data
        first = self.data[data_names[0]]
        reference = data_names[0]  # gets the ± std band

        for dom_name, dom in domains.items():
            # Domain applied to each raw Data (resample domains reproject here);
            # optional timestep pre-aggregation is applied uniformly so each period
            # contributes one value per bucket, then groupby builds the cycle.
            prepared = {}
            for ds_name in data_names:
                d = self.data[ds_name]
                d = dom.apply(d) if dom is not None else d
                obj = time_resampling(
                    d.obj, timestep=timestep, time_interval=time_interval
                )
                prepared[ds_name] = (d, obj)

            for variable in vars:
                dst_unit = vars[variable] if isinstance(vars, dict) else None
                label_unit = (
                    vars[variable]
                    if isinstance(vars, dict)
                    else first.var_unit(variable)
                )

                figure = plt.figure(**self.figure_kwargs(figsize=(8, 5)))
                ax = figure.add_subplot(1, 1, 1)

                xticklabels = None

                for ds_name, (d, obj) in prepared.items():
                    da = obj[variable]
                    if self.plot_config.dim_reduce:
                        da = dim_reduction(da, self.plot_config.dim_reduce)
                    da = da.reduce(
                        self.plot_config.reduction_method.func,
                        list(set(da.dims) - {"time"}),
                    )
                    da = change_unit(da, d.var_unit(variable), dst_unit)

                    grouped = da.groupby(f"time.{time_bucket}")
                    mean = grouped.mean("time", skipna=True)
                    std = grouped.std("time", skipna=True)

                    bucket_vals = mean[time_bucket].values
                    xticklabels = (
                        xticklabels if xticklabels is not None else bucket_vals
                    )

                    ax.plot(bucket_vals, mean.values, label=ds_name)
                    # ± std band only for the reference (first) dataset.
                    if ds_name == reference:
                        ax.fill_between(
                            bucket_vals,
                            (mean - std).values,
                            (mean + std).values,
                            alpha=0.2,
                        )

                title = self.plot_kwargs.get(
                    "title", f"{time_bucket.capitalize()} cycle of {variable}"
                )
                xlabel = self.plot_kwargs.get("xlabel", time_bucket.capitalize())
                ylabel = self.plot_kwargs.get(
                    "ylabel", _unit_label(variable, label_unit)
                )

                ax.set_xlabel(xlabel)
                ax.set_xticks(list(range(len(xticklabels))))
                ax.set_xticklabels(xticklabels)
                ax.set_ylabel(ylabel)
                ax.legend()
                figure.suptitle(title)

                start, end = manage_time_interval(time_interval)
                start = "start" if start is None else start.strftime("%d-%m-%Y")
                end = "end" if end is None else end.strftime("%d-%m-%Y")
                fmt = self.plot_kwargs.get("format", "jpg")
                filename = (
                    f"cycle-{time_bucket}-{dom_name}-{variable}-{start}_{end}.{fmt}"
                    if self.plot_config.filename is None
                    else self.plot_config.filename
                )

                self.savefig(figure, filename)


class CustomPlotConfig(BasePlotConfig):
    """CustomPlotConfig Free-form composition of primitives on shared axes.

    Var-scope is mutually exclusive: EITHER ``vars`` is set at the plot level
    (the whole composition re-renders once per var, every subplot sees that
    var) OR each subplot declares its own ``var`` (a fixed composition — e.g. a
    NO2 contour overlaid with a CO line). Never both.
    """

    type: Literal["custom"]
    # Optional here (unlike BasePlotConfig where vars is required): omitted means
    # every subplot supplies its own var.
    vars: list[str] | dict[str, str] | None = Field(default=None)
    time: str | list[str] | None = Field(default=None)
    timestep: TimestepEnum | None = Field(default=None)
    subplots: list[PrimitiveModel] = Field(min_length=1)

    @model_validator(mode="after")
    def check_var_scope(self) -> "CustomPlotConfig":
        plot_vars_set = self.vars is not None
        subplot_vars = [getattr(sp, "var", None) for sp in self.subplots]
        any_subplot_var = any(v is not None for v in subplot_vars)
        all_subplot_vars = all(v is not None for v in subplot_vars)
        if plot_vars_set and any_subplot_var:
            raise ValueError(
                "custom plot: set 'vars' at the plot level OR a 'var' on every "
                "subplot, not both."
            )
        if not plot_vars_set and not all_subplot_vars:
            raise ValueError(
                "custom plot: when plot-level 'vars' is omitted, every subplot "
                "must declare its own 'var'."
            )
        return self


class Custom(Plot):
    """Custom plot: overlay primitives on one shared set of axes.

    The orchestrator owns all data preparation; primitives only draw. For each
    (time, domain, var) context it prepares each subplot's data — resolve
    dataset/var, apply domain, filter time, per-dim reduce (plot-level merged
    with subplot-level, subplot wins), blanket-reduce the remaining non-axis
    dims, convert units — then calls ``primitive.render`` and assembles the
    figure-level legend/colorbar.
    """

    config = CustomPlotConfig
    aliases = ["custom"]

    def plot(self):
        """plot Render one figure per (time, domain, var) context."""
        domains = self.resolve_domains()
        plot_vars = self.plot_config.vars
        # dict form ({var: unit}) fans out over its keys; None → single None slot.
        var_list = list(plot_vars) if plot_vars is not None else None
        for time_interval, dom_name, dom, var in self.iterate_contexts(
            self.plot_config.time, domains, var_list
        ):
            self._render_composition(time_interval, dom_name, dom, var)

    @staticmethod
    def _resolve_keep_dims(data, x: str | None, y: str | None) -> set[str]:
        """Dims the x/y coordinate names depend on — the axes to preserve.

        Names a *coordinate* (which may be N-D, e.g. RegularGrid ``longitude``
        over ``(y, x)``), falling back to treating the name as a literal dim.
        Everything not returned here gets reduced away before rendering.
        """
        keep: set[str] = set()
        for coord in (x, y):
            if coord is None:
                continue
            if coord in data.coords:
                keep.update(data[coord].dims)
            elif coord in data.dims:
                keep.add(coord)
        return keep

    def _prepare_subplot_data(self, subplot, dom, var, time_interval):
        """Full data-prep pipeline for one subplot; returns the drawable DataArray."""
        data = self.data[subplot.dataset]
        data = dom.apply(data) if dom is not None else data
        da = data.obj[var]

        # Per-subplot time wins over the plot-level iteration time (lets different
        # windows overlay on one figure); falls back to the iteration otherwise.
        effective_time = subplot.time if subplot.time is not None else time_interval
        da = time_resampling(
            da, timestep=self.plot_config.timestep, time_interval=effective_time
        )

        # Per-dim reductions: plot-level defaults merged with subplot overrides.
        merged_dim_reduce = {}
        if self.plot_config.dim_reduce:
            merged_dim_reduce.update(self.plot_config.dim_reduce)
        if subplot.dim_reduce:
            merged_dim_reduce.update(subplot.dim_reduce)
        if merged_dim_reduce:
            da = dim_reduction(da, merged_dim_reduce, name=var)

        # Keep the axis dims (resolved after dim_reduce so dim-dropping selections
        # are reflected); blanket-reduce whatever is left.
        keep = self._resolve_keep_dims(da, subplot.x, subplot.y)
        reduction_dims = [d for d in da.dims if d not in keep]
        if reduction_dims:
            da = da.reduce(subplot.reduction_method.func, reduction_dims)

        # Unit precedence: subplot.unit wins over a plot-level vars-dict unit.
        plot_vars = self.plot_config.vars
        dst_unit = subplot.unit
        if dst_unit is None and isinstance(plot_vars, dict):
            dst_unit = plot_vars.get(var)
        da = change_unit(da, data.var_unit(var), dst_unit)
        return da, dst_unit

    def _render_composition(self, time_interval, dom_name, dom, plot_var):
        figure = plt.figure(**self.figure_kwargs())
        ax = figure.add_subplot(1, 1, 1)

        colorbar = None  # (mappable, label) for the first colour primitive
        has_legend = False
        used_vars = []

        for subplot in self.plot_config.subplots:
            var = plot_var if plot_var is not None else subplot.var
            used_vars.append(var)

            da, dst_unit = self._prepare_subplot_data(subplot, dom, var, time_interval)

            primitive = Primitive.get_primitive_class(subplot.type)(self.name, subplot)
            label = subplot.label if subplot.label is not None else var
            artist = primitive.render(ax, da, x=subplot.x, y=subplot.y, label=label)

            if primitive.wants_colorbar and colorbar is None:
                colorbar = (artist, _unit_label(var, dst_unit))
            if primitive.wants_legend:
                has_legend = True

        if colorbar is not None:
            mappable, clabel = colorbar
            figure.colorbar(mappable, ax=ax, orientation="vertical", label=clabel)
        if has_legend:
            ax.legend()

        figure.suptitle(self.plot_kwargs.get("title", self.name))

        start, end = manage_time_interval(time_interval)
        start = "start" if start is None else start.strftime("%d-%m-%Y")
        end = "end" if end is None else end.strftime("%d-%m-%Y")
        fmt = self.plot_kwargs.get("format", "jpg")
        # var token: the single plot-level var, or the distinct subplot vars
        # (declaration order) joined with "+", e.g. "NO2+CO".
        var_token = (
            plot_var
            if plot_var is not None
            else "+".join(dict.fromkeys(str(v) for v in used_vars))
        )
        filename = (
            f"custom-{dom_name}-{var_token}-{start}_{end}.{fmt}"
            if self.plot_config.filename is None
            else self.plot_config.filename
        )
        self.savefig(figure, filename)
