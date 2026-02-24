from pydantic import BaseModel, Field
import matplotlib.pyplot as plt
from typing import Literal

from ClimateGraph.data import Data, PointSurface, RegularGrid, SatelliteSwath
from ClimateGraph.utils.general_utils import manage_time_interval, TimestepEnum
from .plot import Plot

class TimeSeriesConfig(BaseModel):
    type: Literal["timeseries"]
    base: str
    other_data: str | list[str]
    vars: str | list[str]
    colors: str | None = Field(default=None)
    time_interval: str | list[str] | None  = Field(default=None)
    timestep: TimestepEnum | None = Field(default=None) 

class Timeseries(Plot):
    config = TimeSeriesConfig
    def plot(self):
        other_data = (
            self.plot_config.other_data
            if isinstance(self.plot_config.other_data, list)
            else [self.plot_config.other_data]
        )
        base = self.data[self.plot_config.base]
        other_data = {_data: self.data[_data] for _data in self.plot_config.other_data}
        vars = self.plot_config.vars

        all_data = {
            name_: base.resample_vars(data, vars) for name_, data in other_data.items()
        }  # now every item in list is a dataset resampled with all the vars :)
        all_data[self.plot_config.base] = base.obj

        timestep, time_interval = (
            self.plot_config.timestep,
            self.plot_config.time_interval,
        )

        for name, data_obj in all_data.items():

            if time_interval is not None:
                start, end = manage_time_interval(time_interval)
                data_obj = data_obj.sel({"time": slice(start, end)})
            if timestep is not None:
                data_obj = data_obj.resample(
                    {"time": timestep}
                ).mean()  # TODO: add other methods of resampling in time.

            all_data[name] = data_obj

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
            figure.savefig(
                self.results_path
                / (
                    f"ts-{variable}-{start.strftime("%d/%m/%Y")}-{end.strftime("%d/%m/%Y")}"
                ),
                format="jpg",
                dpi=1000,
            )
