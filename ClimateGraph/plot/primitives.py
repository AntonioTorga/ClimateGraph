from typing import ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, model_validator

from ClimateGraph.utils.general_utils import ReductionMethodEnum

from .primitive import Primitive


def _drop_nan_points(
    x: np.ndarray, y: np.ndarray, vals: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """_drop_nan_points Drop entries whose value is NaN, keeping x/y/value aligned."""
    keep = ~np.isnan(vals)
    return x[keep], y[keep], vals[keep]


class SubplotConfig(BaseModel):
    """SubplotConfig Shared config for every primitive subplot.

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
        missing = sorted(c for c in self.required_coords if getattr(self, c) is None)
        if missing:
            raise ValueError(
                f"{self.type!r} subplot requires coordinate role(s) {missing} "
                f"(set them under the subplot, e.g. x:/y:)."
            )
        return self


class SeriesConfig(SubplotConfig):
    """SeriesConfig A line along one dimension (``x``)."""

    required_coords: ClassVar[frozenset[str]] = frozenset({"x"})
    type: Literal["series", "line"]


class Series(Primitive):
    """Series primitive: a line of the variable along the ``x`` coordinate."""

    config = SeriesConfig
    aliases = ["series", "line"]
    required_coords = frozenset({"x"})
    wants_legend = True

    def render(self, ax, data, *, x, y, label):
        xvals = (
            data[x].values
            if x in data.coords
            else np.arange(data.sizes.get(x, data.size))
        )
        (line,) = ax.plot(xvals, data.values, label=label, **self.style)
        return line


class ContourFillConfig(SubplotConfig):
    """ContourFillConfig A filled contour over a 2-D (``x``, ``y``) grid."""

    required_coords: ClassVar[frozenset[str]] = frozenset({"x", "y"})
    type: Literal["contourf", "contour_fill", "contourfill"]
    levels: int = 10
    cmap: str = "viridis"


class ContourFill(Primitive):
    """ContourFill primitive: a filled contour of the variable on x/y.

    No CRS / projection awareness (unlike ``SpatialOverlay``) — plain axes,
    generic by design. Projection kwargs, if ever needed, flow through
    ``model_extra``.
    """

    config = ContourFillConfig
    aliases = ["contourf", "contour_fill", "contourfill"]
    required_coords = frozenset({"x", "y"})
    wants_colorbar = True

    def render(self, ax, data, *, x, y, label):
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


class PointsConfig(SubplotConfig):
    """PointsConfig A scatter of points at (``x``, ``y``) coloured by value."""

    required_coords: ClassVar[frozenset[str]] = frozenset({"x", "y"})
    type: Literal["points", "scatter"]
    markersize: float = 40.0
    cmap: str = "viridis"
    edgecolor: str | None = "k"
    drop_nans: bool = False


class Points(Primitive):
    """Points primitive: a coordinate scatter coloured by the variable value."""

    config = PointsConfig
    aliases = ["points", "scatter"]
    required_coords = frozenset({"x", "y"})
    wants_colorbar = True

    def render(self, ax, data, *, x, y, label):
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
