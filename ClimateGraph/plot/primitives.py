"""The concrete primitives and their subplot config models."""

from typing import ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, model_validator

from ClimateGraph.utils.general_utils import ReductionMethodEnum

from .primitive import Primitive

_EARTH_RADIUS_M = 6_371_000.0


def _drop_nan_points(
    x: np.ndarray, y: np.ndarray, vals: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Drop entries whose value is NaN, keeping x/y/value aligned."""
    keep = ~np.isnan(vals)
    return x[keep], y[keep], vals[keep]


def _step_metres(lon: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Metres per index step along each array axis of a 2-D lon/lat grid.

    A curvilinear grid has no single spacing along an axis: a degree of
    longitude shrinks with latitude, and on a Lambert or rotated projection
    both coordinates vary along both axes. So the spacing is read off the
    coordinates themselves, cell by cell, using the equirectangular
    approximation — accurate at grid scale, where the cells are small.

    The result is *along-grid* rather than true east/north. On a rotated grid
    the array axes are tilted relative to the meridians and this does not
    correct for it, which is a few degrees over a regional domain.

    Parameters
    ----------
    lon, lat : np.ndarray
        Two-dimensional longitude and latitude, in degrees.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        Metres per index step along the x and y array axes.
    """
    dlon_dy, dlon_dx = np.gradient(lon)
    dlat_dy, dlat_dx = np.gradient(lat)
    coslat = np.cos(np.deg2rad(lat))
    ex = _EARTH_RADIUS_M * np.deg2rad(np.hypot(dlon_dx * coslat, dlat_dx))
    ey = _EARTH_RADIUS_M * np.deg2rad(np.hypot(dlon_dy * coslat, dlat_dy))
    return ex, ey


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


def _axis_arrays(data, x, y):
    """The data and its x/y coordinates as aligned 2-D numpy arrays.

    Transposes to the coordinates' own dim order so ``np.gradient``'s axis 0
    and axis 1 line up with y and x, and meshes 1-D coordinates out to match.
    """
    ydims = data[y].dims if y in data.coords else (y,)
    xdims = data[x].dims if x in data.coords else (x,)
    order = list(dict.fromkeys(ydims + xdims))
    data = data.transpose(*order)

    xv = np.asarray(data[x].values, dtype=float)
    yv = np.asarray(data[y].values, dtype=float)
    if xv.ndim == 1 and yv.ndim == 1:
        xv, yv = np.meshgrid(xv, yv)
    return data, xv, yv


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
    # Optional per-subplot time override. When set it wins over the plot-level
    # `time` for this subplot only, so heterogeneous times can overlay on one
    # figure (e.g. the same date across two years). When None the subplot follows
    # the plot's time iteration.
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

    No CRS / projection awareness (unlike ``SpatialOverlay``) — plain axes,
    generic by design. Projection kwargs, if ever needed, flow through
    ``model_extra``.
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

    Deliberately one colour. The lines carry their values on inline labels, so
    the figure's one colour scale stays free for whatever is drawn underneath —
    a ``contourf`` or a ``raster``.
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
    the position and size its coordinates actually give it. Backed by
    ``pcolormesh`` rather than ``imshow`` because a ``RegularGrid`` carries
    two-dimensional ``latitude``/``longitude`` (a WRF or CHIMERE grid on a
    Lambert projection has latitude varying with ``x``), which ``imshow``
    cannot draw at all; and on the grids it can draw, it ignores the
    coordinate values and so renders uneven spacing as if it were even.
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

    Needs no second variable — the field is the one already being drawn, and
    the arrows show which way it climbs and how steeply.

    Spacing comes from the coordinates, so the result is physical rather than
    per-index: two-dimensional ``latitude``/``longitude`` go through
    ``_step_metres`` and give the gradient per metre; one-dimensional
    coordinates are handed to ``np.gradient`` directly and give it per
    coordinate unit. Setting ``normalize`` drops magnitude entirely and shows
    direction alone, which sidesteps the distinction.
    """

    config = GradientConfig
    aliases = ["gradient", "grad"]
    required_coords = frozenset({"x", "y"})

    def render(self, ax, data, *, x, y, label):
        """Draw arrows along the field's gradient."""
        cfg = self.subplot_config
        data, xv, yv = _axis_arrays(data, x, y)
        values = np.asarray(data.values, dtype=float)

        if np.ndim(data[x].values) == 2:
            ex, ey = _step_metres(xv, yv)
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

    The usual figure is a concentration field underneath with wind over it, so
    transport is visible. Models write the components (``u10``/``v10``);
    station networks report speed and direction, which are converted here.

    Single-coloured: an arrow already carries its magnitude in its length, so
    colouring it too would spend the figure's one colour scale on information
    that is already shown.
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
        data, xv, yv = _axis_arrays(data, x, y)

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
            xv, yv, cv = _drop_nan_points(xv, yv, cv)
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
