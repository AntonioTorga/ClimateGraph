import logging
from abc import ABC, abstractmethod
from pathlib import Path

import matplotlib as mpl
import numpy as np
from pydantic import BaseModel

mpl.use("Agg")
import matplotlib.pyplot as plt

from ClimateGraph.data import Data
from ClimateGraph.domain import Domain
from ClimateGraph.utils.general_utils import normalize_time
from ClimateGraph.utils.registry import RegistryMixin

log = logging.getLogger(__name__)


def _grid_positions(
    lo: float,
    hi: float,
    spec: int | str,
    offset: float = 0.0,
    tick_locs: list[float] | None = None,
) -> list[float]:
    """_grid_positions Where to draw an axis's reference lines.

    Two modes:
    - ``spec == "ticks"``: one line per major tick (``tick_locs``), spaced by the
      median gap between them.
    - ``spec`` an int N: exactly N evenly-spaced *interior* lines — none land on
      the spines — spaced by ``(hi - lo) / (N + 1)``.

    ``offset`` then shifts every position by that fraction of the spacing (0.5 =
    midway between neighbours), and anything pushed outside ``(lo, hi)`` is dropped
    so lines never draw over the frame.

    Parameters
    ----------
    lo, hi : float
        The axis limits.
    spec : int | str
        ``"ticks"`` or the number of interior lines wanted.
    offset : float, optional
        Shift as a fraction of the line spacing, by default 0.0.
    tick_locs : list[float] | None, optional
        Major tick locations, required for the ``"ticks"`` mode.

    Returns
    -------
    list[float]
        Positions to draw lines at, clipped to the axis interior.
    """
    if spec == "ticks":
        base = [t for t in (tick_locs or []) if lo <= t <= hi]
        if len(base) < 2:
            spacing = (hi - lo) if base else 0.0
        else:
            spacing = float(np.median(np.diff(sorted(base))))
    else:
        n = int(spec)
        if n < 1:
            return []
        spacing = (hi - lo) / (n + 1)
        base = list(np.linspace(lo, hi, n + 2)[1:-1])

    shift = offset * spacing
    return [p + shift for p in base if lo < p + shift < hi]


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

        self.output_path = Path(output_path / name)
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

    def resolve_domains(self) -> dict[str, Domain | None]:
        """resolve_domains Select the domains this plot references from the registry.

        Falls back to a single unnamed no-op slot (``{"": None}``) when the plot
        declares no domains, so callers can iterate uniformly.

        Returns
        -------
        dict[str, Domain | None]
            Mapping of domain name to Domain (or ``None`` for the no-op slot).
        """
        domains = {
            name: dom
            for name, dom in self.domains.items()
            if name in self.plot_config.domains
        }
        return domains or {"": None}

    def iterate_contexts(
        self,
        times,
        domains: dict[str, Domain | None],
        vars: list[str] | None,
    ):
        """iterate_contexts Yield the (time, domain, var) render contexts.

        Centralizes the time x domain x var nesting duplicated across the plot
        classes. Time is normalized here (a single date, an interval, or a list
        fanning out into N entries). When ``vars`` is ``None`` a single ``None``
        var slot is yielded per (time, domain) pair — the per-subplot-var-scope
        case where the var is decided downstream.

        Parameters
        ----------
        times : str | list[str] | None
            The plot's ``time`` field (raw), normalized internally.
        domains : dict[str, Domain | None]
            Resolved domains (see ``resolve_domains``).
        vars : list[str] | None
            Variable names to fan out over, or ``None`` for a single ``None`` slot.

        Yields
        ------
        tuple[str | None, str, Domain | None, str | None]
            ``(time_interval, domain_name, domain, var)`` tuples.
        """
        for time_interval in normalize_time(times):
            for dom_name, dom in domains.items():
                if vars is None:
                    yield time_interval, dom_name, dom, None
                else:
                    for var in vars:
                        yield time_interval, dom_name, dom, var

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

    def _decorate_axes(self, figure: mpl.figure.Figure):
        """_decorate_axes Apply the config's axis decoration to every data axes.

        Colorbar axes are skipped. Cartopy ``GeoAxes`` route their grid through
        ``gridlines()`` (a proper geographic graticule) using the same computed
        positions as regular axes, so the count and offset behave identically.
        Named ticks are skipped on GeoAxes — they need an explicit ``crs=``.

        Parameters
        ----------
        figure : mpl.figure.Figure
            The rendered figure, decorated in place.
        """
        grid = getattr(self.plot_config, "grid", None)
        xticks = getattr(self.plot_config, "xticks", None)
        yticks = getattr(self.plot_config, "yticks", None)
        if grid is None and not xticks and not yticks:
            return

        for ax in figure.axes:
            if ax.get_label() == "<colorbar>":
                continue
            is_geo = hasattr(ax, "projection")

            if grid is not None:
                self._apply_grid(ax, grid, is_geo)

            if xticks or yticks:
                if is_geo:
                    log.debug(
                        "Named ticks are not applied to map axes (they need an "
                        "explicit CRS transform); skipping for %r.",
                        self.name,
                    )
                else:
                    if xticks:
                        ax.set_xticks(list(xticks))
                        ax.set_xticklabels(list(xticks.values()))
                    if yticks:
                        ax.set_yticks(list(yticks))
                        ax.set_yticklabels(list(yticks.values()))

    def _apply_grid(self, ax, grid, is_geo: bool):
        """_apply_grid Draw the dashed reference lines on one axes."""
        style = {
            "color": grid.color,
            "alpha": grid.alpha,
            "linestyle": grid.linestyle,
            "linewidth": grid.linewidth,
        }
        positions = {}
        for axis, spec in (("x", grid.x), ("y", grid.y)):
            if spec is None:
                continue
            lo, hi = ax.get_xlim() if axis == "x" else ax.get_ylim()
            ticks = (
                ax.get_xticks().tolist() if axis == "x" else ax.get_yticks().tolist()
            )
            positions[axis] = _grid_positions(lo, hi, spec, grid.offset, ticks)

        if not positions:
            return

        if is_geo:
            locs = {}
            if "x" in positions:
                locs["xlocs"] = positions["x"]
            if "y" in positions:
                locs["ylocs"] = positions["y"]
            ax.gridlines(draw_labels=False, **locs, **style)
            return

        for value in positions.get("x", []):
            ax.axvline(value, zorder=0, **style)
        for value in positions.get("y", []):
            ax.axhline(value, zorder=0, **style)

    def _finalize(self, figure: mpl.figure.Figure, filename: str):
        """_finalize Post-render pipeline: decorate the axes, then write the figure.

        The single place every plot class funnels through once its data is drawn
        (mirrors ``Reader.read -> _postprocess -> _finalize``). Additional
        figure-level decorators hook in here rather than inside ``savefig``,
        which stays a pure writer.

        Parameters
        ----------
        figure : mpl.figure.Figure
            Matplotlib figure to decorate and save.
        filename : str
            Filename to be used. Doesn't have to include file format, just name.
        """
        self._decorate_axes(figure)
        self.savefig(figure, filename)

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
