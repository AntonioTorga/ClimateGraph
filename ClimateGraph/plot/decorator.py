"""Annotations drawn over a finished composition.

A decorator marks up the axes the primitives established — a threshold line, a
shaded episode — rather than drawing data of its own.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel

from ClimateGraph.utils.registry import RegistryMixin

if TYPE_CHECKING:
    import matplotlib as mpl
    import xarray as xr


class Decorator(RegistryMixin, ABC):
    """The Decorator abstract class.

    The second family a ``type: custom`` plot composes. Where a
    :class:`~ClimateGraph.plot.primitive.Primitive` draws data and owns the
    figure's scales, a decorator annotates the axes those primitives
    established. Drawn afterwards

    Data here is optional, lines for example don't need data except if the line
    is a statistic over the data.
    """

    registry: ClassVar[dict[str, type["Decorator"]]] = {}
    aliases: ClassVar[list[str]] = []
    config: ClassVar[type[BaseModel] | None] = None

    wants_legend: ClassVar[bool] = False

    def __init__(self, name: str, decoration_config: BaseModel, **kwargs):
        """Decorator initialization.

        Parameters
        ----------
        name : str
            Name of the owning plot, used for reference / error messages.
        decoration_config : BaseModel
            The concrete decoration config (a ``DecorationConfig`` subclass)
            driving this decorator.
        """
        self.name = name
        self.decoration_config = decoration_config
        self.style = dict(getattr(decoration_config, "model_extra", None) or {})

    @classmethod
    def get_decorator_class(cls, name: str):
        """Look up a registered decorator subclass by name."""
        return cls.get_class(name)

    @classmethod
    def check_decorator_class(cls, name: str) -> bool:
        """Return True if ``type`` names a registered decorator."""
        return cls.check_class(name)

    @abstractmethod
    def draw(
        self,
        ax: "mpl.axes.Axes",
        data: "xr.DataArray | None",
    ) -> "mpl.artist.Artist":
        """Draw the annotation onto ``ax`` and return the artist.

        Parameters
        ----------
        ax : matplotlib Axes
            The shared axes, after the subplots pass
        data : xr.DataArray | None
            The decoration's data with domain, time, per-dim reductions and
            unit applied but *not* reduced to the plot's axes — None when the
            decoration named no dataset.

        Returns
        -------
        matplotlib Artist
            The artist created, so the orchestrator can build the legend.
        """
        pass
