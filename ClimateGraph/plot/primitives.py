"""The concrete primitives and their subplot config models."""

from typing import ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, model_validator

from ClimateGraph.utils.dataset_utils import axis_arrays, drop_nan_points
from ClimateGraph.utils.general_utils import ReductionMethodEnum
from ClimateGraph.utils.geo_utils import step_metres

from .primitive import Primitive


def _quiver(ax, xv, yv, u, v, cfg, style):
    """Thin, optionally normalise, and draw an arrow field.

    Shared by the two arrow primitives, which differ only in where their
    components come from.
    """
    if cfg.thin > 1:
        step = (slice(None, None, cfg.thin),) * np.ndim(xv)
        xv, yv, u, v = xv[step], yv[step], u[step], v[step]
    if cfg.normalize:
        magnitude = np.hypot(u, v)
        with np.errstate(invalid="ignore", divide="ignore"):
            u, v = u / magnitude, v / magnitude
    return ax.quiver(
        xv,
        yv,
        u,
        v,
        scale=cfg.scale,
        pivot=cfg.pivot,
        color=cfg.color,
        **style,
    )


class SubplotConfig(BaseModel):
    """Shared config for every primitive subplot.

    Flattened (not nested) so a ``subplots:`` entry reads naturally in YAML —
    ``type: contourf`` sits next to ``dataset:``/``x:``/``y:`` directly. Extra
    keys are allowed so matplotlib styling (color, linewidth, alpha, ...) flows
    straight through to the primitive's draw call via ``model_extra``.
    """

    model_config = ConfigDict(extra="allow")

    # Coordinate roles the concrete primitive requires (overridden per subclass).
    required_coords: ClassVar[frozenset[str]] = frozenset()

    dataset: str
    var: str | None = None
    x: str | None = None
    y: str | None = None
    # Wins over the plot-level `time` for this subplot alone, so two windows can
    # overlay on one figure. None follows the plot's time iteration.
    time: str | None = None
    dim_reduce: dict[str, str | dict] | None = None
    reduction_method: ReductionMethodEnum = ReductionMethodEnum.mean
    unit: str | None = None
    label: str | None = None

    @model_validator(mode="after")
    def _check_required_coords(self):
        """Check the subplot declares the coordinates this primitive needs."""
        missing = sorted(c for c in self.required_coords if getattr(self, c) is None)
        if missing:
            raise ValueError(
                f"{self.type!r} subplot requires coordinate role(s) {missing} "
                f"(set them under the subplot, e.g. x:/y:)."
            )
        return self


class SeriesConfig(SubplotConfig):
    """A line along one dimension (``x``)."""

    required_coords: ClassVar[frozenset[str]] = frozenset({"x"})
    type: Literal["series", "line"]


class Series(Primitive):
    """Primitive: a line of the variable along the ``x`` coordinate."""

    config = SeriesConfig
    aliases = ["series", "line"]
    required_coords = frozenset({"x"})
    wants_legend = True

    def render(self, ax, data, *, x, y, label):
        """Draw a line along one dimension."""
        xvals = (
            data[x].values
            if x in data.coords
            else np.arange(data.sizes.get(x, data.size))
        )
        (line,) = ax.plot(xvals, data.values, label=label, **self.style)
        return line


class ContourFillConfig(SubplotConfig):
    """A filled contour over a 2-D (``x``, ``y``) grid."""

    required_coords: ClassVar[frozenset[str]] = frozenset({"x", "y"})
    type: Literal["contourf", "contour_fill", "contourfill"]
    levels: int = 10
    cmap: str = "viridis"


class ContourFill(Primitive):
    """Primitive: a filled contour of the variable on x/y.

    Draws on plain axes with no CRS awareness, unlike ``SpatialOverlay``.
    Projection kwargs flow through ``model_extra``.
    """

    config = ContourFillConfig
    aliases = ["contourf", "contour_fill", "contourfill"]
    required_coords = frozenset({"x", "y"})
    wants_colorbar = True

    def render(self, ax, data, *, x, y, label):
        """Draw filled contours over two coordinates."""
        cfg = self.subplot_config
        return data.plot.contourf(
            x=x,
            y=y,
            ax=ax,
            levels=cfg.levels,
            cmap=cfg.cmap,
            add_colorbar=False,
            add_labels=False,
            **self.style,
        )


class ContourConfig(SubplotConfig):
    """Unfilled contour lines over a 2-D (``x``, ``y``) grid."""

    required_coords: ClassVar[frozenset[str]] = frozenset({"x", "y"})
    type: Literal["contour", "contour_lines", "contourlines"]
    levels: int = 10
    colors: str = "black"
    linewidths: float = 1.0
    clabel: bool = True


class Contour(Primitive):
    """Primitive: single-coloured contour lines of the variable on x/y.

    The lines carry their values on inline labels, leaving the figure's one
    colour scale to whatever is drawn underneath — a ``contourf`` or a
    ``raster``.
    """

    config = ContourConfig
    aliases = ["contour", "contour_lines", "contourlines"]
    required_coords = frozenset({"x", "y"})

    def render(self, ax, data, *, x, y, label):
        """Draw contour lines over two coordinates."""
        cfg = self.subplot_config
        contours = data.plot.contour(
            x=x,
            y=y,
            ax=ax,
            levels=cfg.levels,
            colors=cfg.colors,
            linewidths=cfg.linewidths,
            add_colorbar=False,
            add_labels=False,
            **self.style,
        )
        if cfg.clabel:
            ax.clabel(contours, inline=True, fontsize=8)
        return contours


class RasterConfig(SubplotConfig):
    """The raw 2-D field drawn cell by cell, without contouring."""

    required_coords: ClassVar[frozenset[str]] = frozenset({"x", "y"})
    type: Literal["raster", "pcolormesh", "mesh"]
    cmap: str = "viridis"
    vmin: float | None = None
    vmax: float | None = None


class Raster(Primitive):
    """Primitive: the data drawn cell-for-cell on a 2-D plane.

    No contouring and no interpolation — one quadrilateral per grid cell, at
    the position and size its coordinates give it.

    Backed by ``pcolormesh``.
    """

    config = RasterConfig
    aliases = ["raster", "pcolormesh", "mesh"]
    required_coords = frozenset({"x", "y"})
    wants_colorbar = True

    def render(self, ax, data, *, x, y, label):
        """Draw the field as a mesh over two coordinates."""
        cfg = self.subplot_config
        return data.plot.pcolormesh(
            x=x,
            y=y,
            ax=ax,
            cmap=cfg.cmap,
            vmin=cfg.vmin,
            vmax=cfg.vmax,
            add_colorbar=False,
            add_labels=False,
            **self.style,
        )


class GradientConfig(SubplotConfig):
    """Arrows along the gradient of the variable being plotted."""

    required_coords: ClassVar[frozenset[str]] = frozenset({"x", "y"})
    type: Literal["gradient", "grad"]
    thin: int = 1
    normalize: bool = False
    # Point down-slope instead of up it — the direction a thing would flow.
    descending: bool = False
    scale: float | None = None
    color: str = "black"
    pivot: Literal["tail", "mid", "middle", "tip"] = "middle"


class Gradient(Primitive):
    """Primitive: arrows along the gradient of the variable itself.

    Needs no second variable — the field is the one already being drawn.

    Spacing comes from the coordinates, so the result is physical rather than
    per-index: 2-D ``latitude``/``longitude`` go through ``step_metres`` for a
    gradient per metre, 1-D coordinates give one per coordinate unit.
    ``normalize`` drops magnitude and shows direction alone.
    """

    config = GradientConfig
    aliases = ["gradient", "grad"]
    required_coords = frozenset({"x", "y"})

    def render(self, ax, data, *, x, y, label):
        """Draw arrows along the field's gradient."""
        cfg = self.subplot_config
        data, xv, yv = axis_arrays(data, x, y)
        values = np.asarray(data.values, dtype=float)

        if np.ndim(data[x].values) == 2:
            ex, ey = step_metres(xv, yv)
            df_dy, df_dx = np.gradient(values)
            u, v = df_dx / ex, df_dy / ey
        else:
            df_dy, df_dx = np.gradient(values, yv[:, 0], xv[0, :])
            u, v = df_dx, df_dy

        if cfg.descending:
            u, v = -u, -v
        return _quiver(ax, xv, yv, u, v, cfg, self.style)


class ArrowsConfig(SubplotConfig):
    """A vector field from two variables.

    Either the components (``u``/``v``, what a model writes) or polar form
    (``speed``/``direction``, what a station network reports) — one complete
    pair, never both.
    """

    required_coords: ClassVar[frozenset[str]] = frozenset({"x", "y"})
    type: Literal["arrows", "quiver"]
    u: str | None = None
    v: str | None = None
    speed: str | None = None
    direction: str | None = None
    thin: int = 1
    normalize: bool = False
    scale: float | None = None
    color: str = "black"
    pivot: Literal["tail", "mid", "middle", "tip"] = "middle"

    @model_validator(mode="after")
    def _check_one_complete_pair(self):
        """Exactly one of the two spellings, with both of its halves."""
        components = {"u": self.u, "v": self.v}
        polar = {"speed": self.speed, "direction": self.direction}
        has_components = all(v is not None for v in components.values())
        has_polar = all(v is not None for v in polar.values())

        if has_components and has_polar:
            raise ValueError(
                f"{self.type!r} subplot: give either 'u'/'v' or "
                "'speed'/'direction', not both."
            )
        if not has_components and not has_polar:
            given = sorted(
                name
                for name, value in (components | polar).items()
                if value is not None
            )
            raise ValueError(
                f"{self.type!r} subplot needs a complete pair of variables — "
                f"'u' and 'v', or 'speed' and 'direction'. Got {given or 'none'}."
            )
        return self


class Arrows(Primitive):
    """Primitive: a vector field drawn from two variables.

    Models write the components (``u10``/``v10``); station networks report
    speed and direction, which are converted here. Drawn over a concentration
    field, it shows transport.

    Single-coloured: an arrow carries its magnitude in its length already.
    """

    config = ArrowsConfig
    aliases = ["arrows", "quiver"]
    required_coords = frozenset({"x", "y"})

    @classmethod
    def required_vars(cls, subplot_config):
        """Whichever of the two spellings the subplot used."""
        if subplot_config.u is not None:
            return {"u": subplot_config.u, "v": subplot_config.v}
        return {
            "speed": subplot_config.speed,
            "direction": subplot_config.direction,
        }

    def render(self, ax, data, *, x, y, label):
        """Draw the vector field over two coordinates."""
        cfg = self.subplot_config
        data, xv, yv = axis_arrays(data, x, y)

        if "u" in data:
            u = np.asarray(data["u"].values, dtype=float)
            v = np.asarray(data["v"].values, dtype=float)
        else:
            # Meteorological convention: direction is where the wind blows
            # FROM, so the vector points the opposite way.
            theta = np.deg2rad(np.asarray(data["direction"].values, dtype=float))
            speed = np.asarray(data["speed"].values, dtype=float)
            u, v = -speed * np.sin(theta), -speed * np.cos(theta)

        return _quiver(ax, xv, yv, u, v, cfg, self.style)


class PointsConfig(SubplotConfig):
    """A scatter of points at (``x``, ``y``) coloured by value."""

    required_coords: ClassVar[frozenset[str]] = frozenset({"x", "y"})
    type: Literal["points", "scatter"]
    markersize: float = 40.0
    cmap: str = "viridis"
    edgecolor: str | None = "k"
    drop_nans: bool = False


class Points(Primitive):
    """Primitive: a coordinate scatter coloured by the variable value."""

    config = PointsConfig
    aliases = ["points", "scatter"]
    required_coords = frozenset({"x", "y"})
    wants_colorbar = True

    def render(self, ax, data, *, x, y, label):
        """Draw coloured points at two coordinates."""
        cfg = self.subplot_config
        xv = np.asarray(data[x].values).ravel()
        yv = np.asarray(data[y].values).ravel()
        cv = np.asarray(data.values).ravel()
        if cfg.drop_nans:
            xv, yv, cv = drop_nan_points(xv, yv, cv)
        return ax.scatter(
            xv,
            yv,
            c=cv,
            s=cfg.markersize,
            cmap=cfg.cmap,
            edgecolor=cfg.edgecolor,
            label=label,
            **self.style,
        )
