"""Figure generation.

The abstract base for every plot type: resolves the domains a figure runs
under, iterates the time, domain and variable product, and handles axis
decoration and saving so the concrete types only draw.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import matplotlib as mpl
import numpy as np
from pydantic import BaseModel

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.projections.polar import PolarAxes

from ClimateGraph.data import Data
from ClimateGraph.domain import Domain
from ClimateGraph.utils.general_utils import normalize_time
from ClimateGraph.utils.registry import RegistryMixin

log = logging.getLogger(__name__)


def _grid_style(grid) -> dict:
    """Matplotlib line kwargs for the reference lines."""
    return {
        "color": grid.color,
        "alpha": grid.alpha,
        "linestyle": grid.linestyle,
        "linewidth": grid.linewidth,
    }


def _grid_positions(
    lo: float,
    hi: float,
    spec: int | str,
    offset: float = 0.0,
    tick_locs: list[float] | None = None,
) -> list[float]:
    """Where to draw an axis's reference lines.

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
        """Creation of a Plot object with the adequate Plot subclass. Meant to be set and lazily ran.

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
        return plot_class(
            name,
            plot_config=plot_config,
            data_registry=data_registry,
            domain_registry=domain_registry,
            output_path=output_path,
        )

    def __init__(
        self, name, plot_config, data_registry, domain_registry, output_path, **kwargs
    ):
        """Plot initialization dunder method.

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
        # The one place the plot config's extras are read; everything
        # downstream goes through plot_kwargs. Explicit kwargs win, so a
        # caller can override what the control file declared.
        self.plot_kwargs = {**(plot_config.model_extra or {}), **kwargs}

        self.output_path = Path(output_path / name)
        self.output_path.mkdir(parents=True, exist_ok=True)

        self._done = False

    @classmethod
    def check_plot_class(cls, type: str) -> bool:
        """Return True if ``type`` names a registered plot."""
        return cls.check_class(type)

    @classmethod
    def get_plot_class(cls, name: str):
        """Look up a registered plot subclass by name."""
        return cls.get_class(name)

    @abstractmethod
    def plot(self):
        """Abstract method. Run the plot operation with the instance attributes and plot configuration."""
        pass

    def resolve_domains(self) -> dict[str, Domain | None]:
        """Select the domains this plot references from the registry.

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

    def expected_figures(self) -> int:
        """How many figures this plot will write, read off the config alone.

        Every plot type nests time x domains x vars, so the product is exact.
        It opens no file, which is what lets a run report its size up front.

        Returns
        -------
        int
            Number of figures, at least one.
        """
        plot_vars = self.plot_config.vars
        return (
            len(normalize_time(getattr(self.plot_config, "time", None)))
            * len(self.resolve_domains())
            * (len(plot_vars) if plot_vars else 1)
        )

    def figure_kwargs(self, **defaults) -> dict:
        """Build the kwargs for ``plt.figure`` from ``plot_kwargs``.

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
        """Build the kwargs for ``figure.savefig`` from ``plot_kwargs``.

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
        """Apply the config's axis decoration to every data axes.

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
            # On polar axes a vline is a radial spoke and an hline a circle,
            # so the computed Cartesian positions mean nothing.
            is_polar = isinstance(ax, PolarAxes)

            if grid is not None:
                if is_polar:
                    ax.grid(True, **_grid_style(grid))
                else:
                    self._apply_grid(ax, grid, is_geo)

            if xticks or yticks:
                if is_geo or is_polar:
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
        """Draw the dashed reference lines on one axes."""
        style = _grid_style(grid)
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
        """Post-render pipeline: decorate the axes, then write the figure.

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
        """Matplotlib Figure saving. Used by plot function to save to system. Manages kwargs given through the plot configuration relevant to saving.

        Parameters
        ----------
        figure : mpl.figure.Figure
            Matplotlib figure to be saved.
        filename : str
            Filename to be used. Doesn't have to include file format, just name.
        """
        target = self.output_path / filename
        # A filename template may name subdirectories, e.g. "{var}/{domain}".
        target.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(target, **self.savefig_kwargs())

        plt.close(fig=figure)
