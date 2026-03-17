from pydantic import BaseModel, Field
import matplotlib.pyplot as plt
from typing import Literal, List, Dict, Tuple
import numpy as np
import math

from ClimateGraph.data import Data, PointSurface, RegularGrid, SatelliteSwath
from ClimateGraph.utils.general_utils import (
    manage_time_interval,
    TimestepEnum,
    ReductionMethodEnum,
)
from ClimateGraph.utils.dataset_utils import time_resampling

from .plot import Plot


class TimeSeriesConfig(BaseModel):
    type: Literal["timeseries"]
    base: str
    other_data: str | List[str]
    radius_of_influence: int
    vars: str | List[str] | Dict[str, str]
    colors: str | None = Field(default=None)  # TODO: implement
    time_interval: str | List[str] | None = Field(default=None)
    timestep: TimestepEnum | None = Field(default=None)
    filename: str | None = Field(default=None)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)


class Timeseries(Plot):
    config = TimeSeriesConfig

    def plot(self):
        # Get other data to be used in this plot.
        other_data = (
            self.plot_config.other_data
            if isinstance(self.plot_config.other_data, list)
            else [self.plot_config.other_data]
        )

        # Get relevant data from the config
        base = self.data[self.plot_config.base]
        other_data = {_data: self.data[_data] for _data in self.plot_config.other_data}
        vars = self.plot_config.vars
        radius_of_influence = self.plot_config.radius_of_influence
        timestep, time_interval = (
            self.plot_config.timestep,
            self.plot_config.time_interval,
        )

        # Time resampling
        base_obj = time_resampling(
            base.obj, timestep=timestep, time_interval=time_interval
        )
        base_obj = base_obj.rename({name: name + "__" + base.name for name in vars})

        all_data = {
            name_: base.resample_vars(
                data,
                vars,
                radius_of_influence=radius_of_influence,
                timestep=timestep,
                time_interval=time_interval,
            )
            for name_, data in other_data.items()
        }  # now every item in list is a dataset resampled with all the vars :)

        all_data[self.plot_config.base] = base_obj
        # renaming the base object vars so they also have the __{name} at the end.

        # Dimension reduction, TODO: make it so it can be other dim that gets plotted.
        all_data = {
            name: data.reduce(
                self.plot_config.reduction_method.func, list(set(data.dims) - {"time"})
            )
            for name, data in all_data.items()
        }

        # Plotting
        for variable in vars:
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
            ax.set_xlabel("Time")
            ax.set_ylabel(f"{variable}")

            figure.suptitle(f"Timeseries comparison of {variable}")
            start, end = manage_time_interval(time_interval)
            filename = (
                self.plot_config.filename
                if self.plot_config.filename is not None
                else f"ts-{variable}-{start.strftime("%d-%m-%Y")}_{end.strftime("%d-%m-%Y")}.jpg"
            )
            figure.savefig(
                self.output_path / filename,
                format="jpg",
                dpi=1000,
            )


class ScatterConfig(BaseModel):
    type: Literal["scatter"]
    base: str
    other: str
    vars: str | List[str] | Dict[str, str]
    radius_of_influence: int
    time_interval: str
    dimension: str = Field(default="time")
    timestep: TimestepEnum | None = Field(default=None)
    reduction_method: ReductionMethodEnum = Field(default=ReductionMethodEnum.mean)
    filename: str | None = Field(default=None)
    colors: str | None = Field(default=None)  # TODO: implement


class Scatter(Plot):
    config = ScatterConfig

    def plot(self):
        # Get relevant data from the config

        base: Data = self.data[self.plot_config.base]
        other: Data = self.data[self.plot_config.other]
        vars = self.plot_config.vars
        radius_of_influence = self.plot_config.radius_of_influence
        timestep, time_interval = (
            self.plot_config.timestep,
            self.plot_config.time_interval,
        )

        # Time resampling
        base_obj = time_resampling(
            base.obj, timestep=timestep, time_interval=time_interval
        )
        base_obj = base_obj.rename({name: name + "__" + base.name for name in vars})

        other_obj = base.resample_vars(
            other,
            vars,
            radius_of_influence=radius_of_influence,
            timestep=timestep,
            time_interval=time_interval,
        )

        # Dimension reduction, TODO: make it so it can be other dim that gets plotted.
        base_obj = base_obj.reduce(
            self.plot_config.reduction_method.func,
            list(set(base_obj.dims) - {self.plot_config.dimension}),
        )
        other_obj = other_obj.reduce(
            self.plot_config.reduction_method.func,
            list(set(other_obj.dims) - {self.plot_config.dimension}),
        )

        # Plotting
        for variable, unit in vars.items():
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

            ax.set_xlim(min_val, max_val)
            ax.set_ylim(min_val, max_val)
            ax.set_xlabel(f"{variable} [{unit}], {base.name}")
            ax.set_ylabel(f"{variable} [{unit}], {other.name}")
            ax.scatter(base_var.values, other_var.values)

            x = [min_val + x * (max_val - min_val) / 5 for x in range(5 + 1)]
            ax.plot(x, x)

            figure.suptitle(
                f"Scatter comparison of {variable} between {base.name} and {other.name}"
            )
            start, end = manage_time_interval(time_interval)
            filename = (
                self.plot_config.filename
                if self.plot_config.filename is not None
                else f"scatter-{variable}-{start.strftime("%d-%m-%Y")}_{end.strftime("%d-%m-%Y")}.jpg"
            )
            figure.savefig(
                self.output_path / filename,
                format="jpg",
                dpi=1000,
            )
