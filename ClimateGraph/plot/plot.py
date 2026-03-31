from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Annotated, Union, List
import logging
from pathlib import Path
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt

from ClimateGraph.data import Data
from ClimateGraph.domain import Domain

logging.basicConfig(level=logging.INFO)  # TODO: make this settable from yaml file.


class Plot(ABC):
    """The Plot abstract class.

    A class that abstracts the plot definition and interface.
    This class contains and implements attributes and methods common to all the plot subclasses.
    """

    registry: dict[str, type["Plot"]] = dict()
    aliases: List[str] = list()
    config: type["BaseModel"] | None = None

    def __init_subclass__(cls, **kwargs):
        """__init_subclass__ This Dunder method is being used to dinamically register all inheriting classes from Plot, this helps with Plot creation."""
        super().__init_subclass__(**kwargs)
        for name in cls.aliases:
            Plot.registry[name] = cls
        Plot.registry[cls.__name__.lower()] = cls

    @classmethod
    def build_config_union(cls) -> Annotated:
        """build_config_union Build an Annotated Union object used for the Pydantic model.

        Returns
        -------
        Annotated
            Used for the Pydantic model, dicriminates by type used when creating the Plot objects.
        """
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
        domain_registry: dict[str, Domain],
        output_path: Path,
    ) -> "Plot":
        """create Creation of a Plot object with the adequate Plot subclass. Meant to be set and lazily ran.

        Parameters
        ----------
        name : str
            Name of the object, used for reference inside ClimateGraph execution.
        type : str
            Type of Plot, used for lookup in the Plot registry.
        plot_config : BaseModel
            BaseModel object of the corresponding config as a Pydantic model. Used as arguments for the actual plotting.
        data_registry : dict[str, Data]
            Dictionary with all the Data references so Plot's can use them for plotting.
        domain_registry : dict[str, Domain]
            Dictionary with all the Domain references so Plot's can use them for plotting.
        output_path : Path
            Path in which to leave the plot results.

        Returns
        -------
        Plot
            _description_
        """
        plot_class = cls.get_plot_class(type)
        kwargs = plot_config.model_extra if plot_config.model_extra else {}

        return plot_class(
            name,
            plot_config=plot_config,
            data_registry=data_registry,
            domain_registry=domain_registry,
            output_path=output_path,
            **kwargs,
        )

    def __init__(
        self, name, plot_config, data_registry, domain_registry, output_path, **kwargs
    ):
        """__init__ Plot initialization dunder method.

        Parameters
        ----------
        name : str
            Name of the object, used for reference inside ClimateGraph execution.
        plot_config : BaseModel
            BaseModel object of the corresponding config as a Pydantic model. Used as arguments for the actual domain handling.
        data_registry : dict[str, Data]
            Dictionary with all the Data references so Plot's can use them for plotting.
        domain_registry : dict[str, Domain]
            Dictionary with all the Domain references so Plot's can use them for plotting.
        output_path : Path
            Path in which to leave the plot results.
        """
        self.plot_config = plot_config

        self.name = name
        self.data = data_registry
        self.domains = domain_registry
        self.plot_kwargs = kwargs

        self.output_path = Path(
            output_path
            / name  # This is going to be the appk output path + name of plot group
        )
        self.output_path.mkdir(parents=True, exist_ok=True)

        self._done = False

    @classmethod
    def check_plot_class(cls, type: str) -> bool:
        """check_plot_class Method for checking if a string correlates to a Plot subclass, meant to have the same lookup mechanism as get_plot_class

        Parameters
        ----------
        type : str
            String to lookup in Plot class registry.

        Returns
        -------
        bool
            Boolean representing whether the type string corresponds to any Plot subclass.
        """
        return type.lower() in cls.registry

    @classmethod
    def get_plot_class(cls, name: str):
        """get_plot_class Method for getting a class object from a string, centralizes the lookup operation for further development of smart lookup.

        Parameters
        ----------
        name : str
            String to lookup in Plot class registry.

        Returns
        -------
        type
            Class object of adequate plot subclass.
        """
        return cls.registry[name.lower()]

    @abstractmethod
    def plot(self):
        """plot Abstract method. Run the plot operation with the instance attributes and plot configuration."""
        pass

    def savefig(self, figure: mpl.figure.Figure, filename: str):
        """savefig Matplotlib Figure saving. Used by plot function to save to system. Manages kwargs given through the plot configuration relevant to saving.

        Parameters
        ----------
        figure : mpl.figure.Figure
            Matplotlib figure to be saved.
        filename : str
            Filename to be used. Doesn't have to include file format, just name.
        """
        figure.savefig(
            self.output_path / filename,
            dpi=self.plot_config.dpi,
            format=self.plot_config.format,
            transparent=self.plot_config.transparent,
        )

        plt.close(fig=figure)
