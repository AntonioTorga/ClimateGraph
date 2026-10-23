"""Drawable units for composed figures.

A primitive draws one layer onto shared axes, which is what a ``custom`` plot
composes.
"""

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
        """Primitive initialization.

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
        """Look up a registered primitive subclass by name."""
        return cls.get_class(name)

    @classmethod
    def check_primitive_class(cls, name: str) -> bool:
        """Return True if ``type`` names a registered primitive."""
        return cls.check_class(name)

    @classmethod
    def required_vars(cls, subplot_config: BaseModel) -> dict[str, str]:
        """Variables this primitive needs beyond the plot's own, by role.

        Empty for the single-variable primitives, which read the plot's or the
        subplot's ``var``. When it is non-empty the orchestrator prepares each
        named variable through the same pipeline and hands ``render`` an
        ``xr.Dataset`` keyed by role rather than a lone array.

        A classmethod taking the config, not a class attribute, because a
        primitive may accept alternative spellings of the same requirement —
        ``arrows`` takes either ``u``/``v`` or ``speed``/``direction``, so the
        answer depends on what was written.

        Parameters
        ----------
        subplot_config : BaseModel
            The subplot config to read the variable names off.

        Returns
        -------
        dict[str, str]
            Role name to variable name.
        """
        return {}

    @abstractmethod
    def render(
        self,
        ax: "mpl.axes.Axes",
        data: "xr.DataArray | xr.Dataset",
        *,
        x: str | None,
        y: str | None,
        label: str | None,
    ) -> "mpl.artist.Artist":
        """Draw the prepared data onto ``ax`` and return the artist.
        Data could be a datarray if a two or more arrays are needed. E.G. wind arrows

        Parameters
        ----------
        ax : matplotlib Axes
            The shared axes to draw on.
        data : xr.DataArray | xr.Dataset
            Fully prepared data (domain/time/dim-reduce/unit already applied).
            A Dataset keyed by role when the primitive declares
            ``required_vars``, the plot's variable as a lone array otherwise.
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
