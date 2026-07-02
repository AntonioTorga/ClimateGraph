from abc import ABC, abstractmethod
from pathlib import Path

import matplotlib as mpl
from pydantic import BaseModel

mpl.use("Agg")
import matplotlib.pyplot as plt

from ClimateGraph.data import Data
from ClimateGraph.domain import Domain
from ClimateGraph.utils.registry import RegistryMixin

# Which keys in plot_kwargs get routed to which matplotlib call. A given key
# may legitimately belong to more than one sink (e.g. `dpi` applies to both
# the figure and savefig), so the sets overlap on purpose. matplotlib rejects
# kwargs it doesn't recognise (plt.figure -> Figure.set() AttributeError,
# savefig -> TypeError), so we can't blindly splat all of plot_kwargs into
# them; anything not listed here (titles, axis labels, ...) is left for the
# individual plot methods to consume.
FIGURE_KWARGS = {
    "figsize",
    "dpi",
    "layout",
    "facecolor",
    "edgecolor",
    "frameon",
    "linewidth",
}
SAVEFIG_KWARGS = {
    "dpi",
    "format",
    "transparent",
    "bbox_inches",
    "pad_inches",
    "facecolor",
    "edgecolor",
    "orientation",
}


class Plot(RegistryMixin, ABC):
    """The Plot abstract class.

    A class that abstracts the plot definition and interface.
    This class contains and implements attributes and methods common to all the plot subclasses.
    """

    registry: dict[str, type["Plot"]] = dict()
    aliases: list[str] = list()
    config: type["BaseModel"] | None = None

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
        return cls.check_class(type)

    @classmethod
    def get_plot_class(cls, name: str):
        return cls.get_class(name)

    @abstractmethod
    def plot(self):
        """plot Abstract method. Run the plot operation with the instance attributes and plot configuration."""
        pass

    def figure_kwargs(self, **defaults) -> dict:
        """figure_kwargs Build the kwargs for ``plt.figure`` from ``plot_kwargs``.

        Picks the figure-relevant keys (see ``FIGURE_KWARGS``) out of the
        user-supplied ``plot_kwargs`` and layers them on top of any ``defaults``
        the caller passes, so a plot method only has to write
        ``plt.figure(**self.figure_kwargs(figsize=(8, 5)))`` instead of a
        per-key ``.get`` for each matplotlib knob.

        Parameters
        ----------
        **defaults
            Per-plot fallbacks (e.g. ``figsize``) used when the user didn't
            supply that key in the YAML.

        Returns
        -------
        dict
            Kwargs ready to splat into ``plt.figure``.
        """
        merged = {"figsize": (6, 6), "layout": "constrained", **defaults}
        merged.update({k: v for k, v in self.plot_kwargs.items() if k in FIGURE_KWARGS})
        return merged

    def savefig_kwargs(self, **defaults) -> dict:
        """savefig_kwargs Build the kwargs for ``figure.savefig`` from ``plot_kwargs``.

        Same idea as ``figure_kwargs`` but for the save-relevant keys (see
        ``SAVEFIG_KWARGS``).

        Returns
        -------
        dict
            Kwargs ready to splat into ``figure.savefig``.
        """
        merged = {"dpi": 400, "format": "jpg", "transparent": False, **defaults}
        merged.update(
            {k: v for k, v in self.plot_kwargs.items() if k in SAVEFIG_KWARGS}
        )
        return merged

    def savefig(self, figure: mpl.figure.Figure, filename: str):
        """savefig Matplotlib Figure saving. Used by plot function to save to system. Manages kwargs given through the plot configuration relevant to saving.

        Parameters
        ----------
        figure : mpl.figure.Figure
            Matplotlib figure to be saved.
        filename : str
            Filename to be used. Doesn't have to include file format, just name.
        """
        figure.savefig(self.output_path / filename, **self.savefig_kwargs())

        plt.close(fig=figure)
