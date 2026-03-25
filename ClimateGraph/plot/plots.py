from pydantic import BaseModel, Field
import matplotlib.pyplot as plt
from typing import Literal, List, Dict, Tuple
import numpy as np
import math
import cartopy.feature as cfeature
import matplotlib as mpl

from ClimateGraph.data import Data, PointSurface, RegularGrid, SatelliteSwath
from ClimateGraph.utils.general_utils import (
    manage_time_interval,
    TimestepEnum,
    ReductionMethodEnum,
    CRSEnum
)
from ClimateGraph.utils.dataset_utils import time_resampling, change_unit

from .plot import Plot

# TODO: remove nans

class BasePlotConfig(BaseModel):
    filename: str | None = Field(default=None)
    figsize: Tuple[float, float] = Field((6,6))
    format: str = Field(default="jpg")
    layout: Literal['constrained', 'compressed', 'tight', 'none'] | mpl.LayoutEngine | None = Field(default=None)
    dpi: int = Field(default=100)
    transparent: bool = Field(default=False)

class TimeSeriesConfig(BasePlotConfig):
    type: Literal["timeseries", "ts", "time-series"]
    base: str
    other_data: str | List[str]
    radius_of_influence: int
    vars: str | List[str] | Dict[str, str]
    time_interval: str | List[str] | None = Field(default=None)
    timestep: TimestepEnum | None = Field(default=None)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)
    colors: str | None = Field(default=None)  # TODO: implement

class Timeseries(Plot):
    config = TimeSeriesConfig
    aliases = ["ts", "time-series"]

    def plot(self):
        # TODO: remove time intervals with nan values.

        # Get relevant data from the config
        vars = self.plot_config.vars
        radius_of_influence = self.plot_config.radius_of_influence
        timestep = self.plot_config.timestep
        time_interval = self.plot_config.time_interval
        
        if not isinstance(self.plot_config.other_data, list): self.plot_config.other_data = [self.plot_config.other_data]
        other_data = {name: self.data[name] for name in self.plot_config.other_data}
        base = self.data[self.plot_config.base]

        # Working on base data. 
        # 1) Time resampling.  
        # 2) Converting units if necessary. 
        # 3) Renaming so it meets same standard as resampled data.

        base_obj = time_resampling(
            base.obj, timestep=timestep, time_interval=time_interval
        )
        for var in vars:
            if isinstance(vars, dict): base_obj[var] = change_unit(base_obj[var], base.vars[var]["unit"], vars[var])
        base_obj = base_obj.rename({name: name + "__" + base.name for name in vars})

        # Working on the rest of the data. Time and spatial resampling, and converting units.
        other_data = {
            name_: base.resample_vars(
                data,
                vars,
                radius_of_influence=radius_of_influence,
                timestep=timestep,
                time_interval=time_interval,
            )
            for name_, data in other_data.items()
        }  # now every item in list is a dataset resampled with all the vars :)

        other_data[self.plot_config.base] = base_obj # add the base data

        # Dimension reduction, TODO: make it so it can be other dim that gets plotted.
        all_data = {
            name: data.reduce(
                self.plot_config.reduction_method.func, list(set(data.dims) - {"time"})
            )
            for name, data in other_data.items()
        }
        
        # Plotting
        for variable in vars:
            unit = base.vars[variable]["unit"] if not isinstance(vars, dict) else vars[variable]
            figure = plt.figure(
                figsize=self.plot_kwargs.get("figsize", [6, 6]),
                layout=self.plot_kwargs.get("layout", "constrained"),
            )
            ax = figure.add_subplot(1, 1, 1)

            for name, data_obj in all_data.items():
                obj_var = data_obj[f"{variable}__{name}"]
                line = obj_var.plot.line(ax=ax)
                line[0].set_label(name)

            ax.legend()
            
            title = self.plot_kwargs.get("title", f"Timeseries comparison of {variable}")
            xlabel = self.plot_kwargs.get("xlabel", "Time")
            ylabel = self.plot_kwargs.get("ylabel", f"{variable} ({unit})")

            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            figure.suptitle(title)
            
            start, end = manage_time_interval(time_interval)
            format = self.plot_kwargs.get("format", "jpg")
            filename = f"ts-{variable}-{start.strftime("%d-%m-%Y")}_{end.strftime("%d-%m-%Y")}.{format}" if self.plot_config.filename is None else self.plot_config.filename
            
            self.savefig(filename)


class ScatterConfig(BasePlotConfig):
    type: Literal["scatter", "sc"]
    base: str
    other: str
    vars: str | List[str] | Dict[str, str]
    radius_of_influence: int
    time_interval: str
    dimension: str = Field(default="time")
    timestep: TimestepEnum | None = Field(default=None)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)
    colors: str | None = Field(default=None)  # TODO: implement

class Scatter(Plot):
    config = ScatterConfig
    aliases = ["sc"]

    def plot(self):
        # Get relevant data from the config
        base = self.data[self.plot_config.base]
        other = self.data[self.plot_config.other]
        vars = self.plot_config.vars
        radius_of_influence = self.plot_config.radius_of_influence
        timestep = self.plot_config.timestep
        time_interval =self.plot_config.time_interval

        # Managing base data: 
        # 1) Time resampling and alignment
        # 2) Change measure units accordingly
        # 3) Reducing dimensionality

        base_obj = time_resampling(
            base.obj, timestep=timestep, time_interval=time_interval
        )
        for var in vars:
            unit =  base.vars[var]["unit"] if isinstance(vars, List | str) else vars[var]
            base_obj[var] = change_unit(base_obj[var], base.vars[var]["unit"], vars[var])
        
        base_obj = base_obj.rename({name: name + "__" + base.name for name in vars})
        base_obj = base_obj.reduce(
            self.plot_config.reduction_method.func,
            list(set(base_obj.dims) - {self.plot_config.dimension}),
        )

        # Managing other data:
        # 1) Space and time resampling. Time alignment.
        # 2) Dimensionality reduction. 

        other_obj = base.resample_vars(
            other,
            vars,
            radius_of_influence=radius_of_influence,
            timestep=timestep,
            time_interval=time_interval,
        )

        other_obj = other_obj.reduce(
            self.plot_config.reduction_method.func,
            list(set(other_obj.dims) - {self.plot_config.dimension}),
        )

        # Plotting
        for variable, unit in vars.items():
            unit =  base.vars[variable]["unit"] if isinstance(vars, List | str) else vars[var]
            figure = plt.figure(
                figsize=self.plot_kwargs.get("figsize", [6, 6]),
                layout=self.plot_kwargs.get("layout", "constrained"),
            )
            base_var, other_var = (
                base_obj[f"{variable}__{base.name}"],
                other_obj[f"{variable}__{other.name}"],
            )
            ax = figure.add_subplot(1, 1, 1)
            min_val, max_val = math.floor(
                np.nanmin([np.nanmin(base_var), np.nanmin(other_var)])
            ), math.ceil(np.nanmax([np.nanmax(base_var), np.nanmax(other_var)]))

            title = self.plot_kwargs.get("title", f"Scatter comparison of {variable} between {base.name} and {other.name}")
            xlabel = self.plot_kwargs.get("xlabel", f"{variable} [{unit}], {base.name}")
            ylabel = self.plot_kwargs.get("ylabel", f"{variable} [{unit}], {other.name}")

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
            filename = f"scatter-{variable}-{start.strftime("%d-%m-%Y")}_{end.strftime("%d-%m-%Y")}.{format}" if self.plot_config.filename is None else self.plot_config.filename
            
            self.savefig(filename)

class SpatialOverlayConfig(BasePlotConfig):
    type: Literal["spatial-overlay", "spatialoverlay", "so"]
    base: str
    superposed: str
    vars: str | List[str] | Dict[str, str]
    time_interval: str
    levels: int = Field(default=10)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)
    crs: CRSEnum | None = Field(default=None)
    coastlines: bool = Field(default=True)
    borders: bool = Field(default=True)
    cmap: str = Field(default="viridis")

class SpatialOverlay(Plot):
    aliases = ["spatial-overlay", "spatialoverlay", "so"]
    config = SpatialOverlayConfig

    def plot(self):
        # Get relevant data from the config
        base: RegularGrid = self.data[self.plot_config.base]
        superposed: PointSurface = self.data[self.plot_config.superposed]
        vars = self.plot_config.vars
        time_interval = self.plot_config.time_interval
        crs = base.crs.crs if self.plot_config.crs is None else self.plot_config.crs.crs #TODO: make this simpler haha

        for var in vars:
            base_var = base.obj[var]
            superposed_var = superposed.obj[var]
            unit = base.vars[var]["unit"] if isinstance(vars, list|str) else vars[var]

            # Time alignment
            base_var = time_resampling(base_var, time_interval=time_interval)
            superposed_var = time_resampling(superposed_var, time_interval=time_interval)
            
            # Reduction
            base_reduction_dims = [x for x in ["time", "z"] if x in base.dims]
            base_var = base_var.reduce(self.plot_config.reduction_method.func, base_reduction_dims)
            superposed_var = superposed_var.reduce(self.plot_config.reduction_method.func, "time")
            
            # unit conversion
            base_var = change_unit(base_var, base.vars[var]["unit"], unit)
            superposed_var = change_unit(superposed_var, superposed.vars[var]["unit"], unit)
            
            # Plotting
            figure = plt.figure(
                figsize=self.plot_kwargs.get("figsize", [6, 6]),
                layout=self.plot_kwargs.get("layout", "constrained"),
            )
            ax = figure.add_subplot(1,1,1, projection=crs())

            if self.plot_config.coastlines: ax.coastlines()
            if self.plot_config.borders: ax.add_feature(cfeature.BORDERS)

            figure.suptitle(f"Spatial overlay comparison of {var} between {base.name} and {superposed.name}")
    
            vmin, vmax = np.nanmin([base_var.min(), superposed_var.min()]),  np.nanmax([base_var.max(), superposed_var.max()])
            lon_min = np.nanmax([np.nanmin(base_var["longitude"]), np.nanmin(superposed_var["longitude"])])
            lat_min = np.nanmax([np.nanmin(base_var["latitude"]), np.nanmin(superposed_var["latitude"])])
            lon_max = np.nanmin([np.nanmax(base_var["longitude"]), np.nanmax(superposed_var["longitude"])])
            lat_max = np.nanmin([np.nanmax(base_var["latitude"]), np.nanmax(superposed_var["latitude"])])

            norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
            ax.contourf(base_var["longitude"].values, base_var["latitude"].values , base_var.values, transform= base.crs.crs(),
                    cmap=self.plot_config.cmap ,norm=norm, levels=self.plot_config.levels)
            
            ax.scatter(superposed_var["longitude"].values, superposed_var["latitude"].values, c=superposed_var.values,
                transform = superposed.crs.crs(), cmap=self.plot_config.cmap, norm=norm, edgecolor="k")

            ax.set_extent(
                [lon_min, lon_max, lat_min, lat_max],
                crs=crs()
                ) #TODO: when the domains module is done, replace with the domain boundaries
            sm = mpl.cm.ScalarMappable(norm=norm, cmap=self.plot_config.cmap).set_array([])

            figure.colorbar(sm, ax=ax, orientation="vertical", label=f"{var} [{unit}]")

            start, end = manage_time_interval(time_interval)
            format = self.plot_kwargs.get("format", "jpg")
            filename = (f"spatial_overlay-{var}-{base.name}-{superposed.name}-{start.strftime("%d-%m-%Y")}_{end.strftime("%d-%m-%Y")}.{format}" if self.plot_config.filename is None else self.plot_config.filename)
            
            self.savefig(filename)
