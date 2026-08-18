from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel

from ClimateGraph.utils.registry import RegistryMixin

if TYPE_CHECKING:
    import matplotlib as mpl
    import xarray as xr


class Primitive(RegistryMixin, ABC):
    """The Primitive abstract class.

    A minimal rendering unit — the atomic building block of a ``type: custom``
    plot. A primitive does no data processing of its own: the plot orchestrator
    resolves the dataset/var, applies the domain, filters time, reduces dims and
    converts units, then hands the prepared ``xr.DataArray`` to ``render`` along
    with the coordinate names bound to each axis. The primitive only draws and
    returns the matplotlib artist, so legends and colorbars stay a figure-level
    concern of the orchestrator.

    Mirrors the ``Plot`` / ``Domain`` ABC + registry shape via ``RegistryMixin``:
    concrete primitives self-register by class name and ``aliases``, and their
    ``config`` classes are gathered into a discriminated union by
    ``build_config_union``.
    """

    registry: ClassVar[dict[str, type["Primitive"]]] = {}
    aliases: ClassVar[list[str]] = []
    config: ClassVar[type[BaseModel] | None] = None

    required_coords: ClassVar[frozenset[str]] = frozenset()
    wants_colorbar: ClassVar[bool] = False
    wants_legend: ClassVar[bool] = False

    def __init__(self, name: str, subplot_config: BaseModel, **kwargs):
        """__init__ Primitive initialization.

        Parameters
        ----------
        name : str
            Name of the owning plot, used for reference / error messages.
        subplot_config : BaseModel
            The concrete subplot config (a ``SubplotConfig`` subclass) driving
            this primitive.
        """
        self.name = name
        self.subplot_config = subplot_config
        self.style = dict(getattr(subplot_config, "model_extra", None) or {})

    @classmethod
    def get_primitive_class(cls, name: str):
        return cls.get_class(name)

    @classmethod
    def check_primitive_class(cls, name: str) -> bool:
        return cls.check_class(name)

    @abstractmethod
    def render(
        self,
        ax: "mpl.axes.Axes",
        data: "xr.DataArray",
        *,
        x: str | None,
        y: str | None,
        label: str | None,
    ) -> "mpl.artist.Artist":
        """render Draw the prepared data onto ``ax`` and return the artist.

        Parameters
        ----------
        ax : matplotlib Axes
            The shared axes to draw on.
        data : xr.DataArray
            Fully prepared data (domain/time/dim-reduce/unit already applied).
        x : str | None
            Coordinate name bound to the x axis.
        y : str | None
            Coordinate name bound to the y axis (None for 1-D primitives).
        label : str | None
            Legend / colorbar label for this artist.

        Returns
        -------
        matplotlib Artist
            The artist created, so the orchestrator can build legends/colorbars.
        """
        pass
