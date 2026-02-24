from . import plots
from ClimateGraph.data import Data


from abc import ABC, abstractmethod
from pydantic import BaseModel, Field, TypeAdapter
from typing import Annotated, Union, Tu
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)  # TODO: make this settable from yaml file.


class Plot:
    registry: dict[str, type["Plot"]] = dict()
    config: type["BaseModel"] | None = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Plot.registry[cls.__name__.lower()] = cls

    @classmethod
    def build_config_union(cls) -> Annotated:
        configs = [
            cls.config for cls in Plot.registry.values() if cls.config is not None
        ]
        return Annotated[Union[tuple(configs)], Field(discriminator="type")]

    @classmethod
    def create(
        cls,
        type: str,
        name: str,
        plot_dict: dict,
        data_registry: dict[str, Data],
        output_path: Path,
    ):
        if type.lower() not in cls.registry:
            raise ValueError(
                f"No plot type named {type} supported.\nSupported types are {list(cls.registry.keys())}"
            )
        plot_class = cls.get_plot_class(type)
        config_model = plot_class.config
        if not (
            model_valid := config_model.model_validate(plot_dict)
        ):  # TODO: assume that the config is received

            raise ValueError(
                f"Plot called {name} doesn't meet the input model for {type} plot."
            )

        return plot_class(
            name,
            plot_config=model_valid,
            data_registry=data_registry,
            output_path=output_path,
            **model_valid.model_extra,
        )

    def __init__(self, name, plot_config, data_registry, output_path, **kwargs):
        self.plot_config = plot_config

        self.name = name
        self.data = data_registry
        self.output_path = (
            output_path  # This is going to be the appk output path + name of plot group
        )
        self.plot_kwargs = kwargs

        self._done = False

    @classmethod
    def check_plot_class(cls, type: str):
        return type.lower() in cls.registry

    @classmethod
    def get_plot_class(cls, name: str):
        return cls.registry[name.lower()]

    @abstractmethod
    def plot(self):
        pass
