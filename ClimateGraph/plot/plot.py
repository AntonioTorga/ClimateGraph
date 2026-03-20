from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Annotated, Union, List
import logging
from pathlib import Path

from ClimateGraph.data import Data

logging.basicConfig(level=logging.INFO)  # TODO: make this settable from yaml file.


class Plot(ABC):
    registry: dict[str, type["Plot"]] = dict()
    aliases: List[str] = list()
    config: type["BaseModel"] | None = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for name in cls.aliases:
            Plot.registry[name] = cls
        Plot.registry[cls.__name__.lower()] = cls

    @classmethod
    def build_config_union(cls) -> Annotated:
        configs = [
            cls_.config for cls_ in Plot.registry.values() if cls_.config is not None
        ]
        return Annotated[Union[tuple(configs)], Field(discriminator="type")]

    @classmethod
    def create(
        cls,
        name: str,
        type: str,
        plot_config: BaseModel,
        data_registry: dict[str, Data],
        output_path: Path,
    ):
        plot_class = cls.get_plot_class(type)
        kwargs = plot_config.model_extra if plot_config.model_extra else {}

        return plot_class(
            name,
            plot_config=plot_config,
            data_registry=data_registry,
            output_path=output_path,
            **kwargs,
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
