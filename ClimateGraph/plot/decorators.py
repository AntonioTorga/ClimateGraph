"""The concrete decorators and their config models."""

from typing import Literal

import numpy as np
from pydantic import ConfigDict, field_validator, model_validator

from ClimateGraph.utils.general_utils import (
    ExpandableModel,
    ReferenceEnum,
    manage_time_interval,
)

from .decorator import Decorator

_PERCENTILES = {"p10": 10, "p25": 25, "p75": 75, "p90": 90, "p95": 95, "p99": 99}


def _reference_value(data, at, coord: str | None = None):
    """Resolve a reference position to a single value.

    ``at`` is either a literal or a statistic in 
    :class:`~ClimateGraph.utils.general_utils.ReferenceEnum`  computed
    from ``data``. Dates go through ``manage_time_interval`` so they are read
    dayfirst like every other date in a control file.

    ``argmax``/``argmin`` are the exception: they return the value of ``coord``
    at which the extreme occurs rather than the extreme itself, which is what a
    vertical line wants.

    Parameters
    ----------
    data : xr.DataArray | None
        The decoration's unreduced data, or None when ``at`` is a literal.
    at : float | ReferenceEnum | str
        The position, or the statistic to compute it with.
    coord : str | None
        Coordinate the position is reported on, needed only by argmax/argmin.

    Returns
    -------
    float | pd.Timestamp
        The axis position to draw at.
    """
    if isinstance(at, bool):
        raise TypeError(f"'at' must be a number, a date or a statistic, got {at!r}.")
    if isinstance(at, int | float):
        return at
    if not isinstance(at, ReferenceEnum):
        start, _ = manage_time_interval(at)
        return start

    if data is None:
        raise ValueError(
            f"'at: {at.value}' is a statistic of the data, but no dataset was given."
        )
    values = np.asarray(data.values, dtype=float)

    if at in (ReferenceEnum.argmax, ReferenceEnum.argmin):
        if coord is None or coord not in data.coords:
            raise ValueError(
                f"'at: {at.value}' reports where the extreme occurs, so it needs 'x' "
                f"to name a coordinate of the data. Got {coord!r}."
            )
        positions = np.asarray(data[coord].values).ravel()
        if positions.size != values.size:
            raise ValueError(
                f"'at: {at.value}' needs {coord!r} to line up one-to-one with the "
                f"data ({positions.size} positions for {values.size} values). "
                "Reduce the other dimensions with 'dim_reduce' first."
            )
        picker = np.nanargmax if at is ReferenceEnum.argmax else np.nanargmin
        return positions[int(picker(values))]

    if at.value in _PERCENTILES:
        return float(np.nanpercentile(values, _PERCENTILES[at.value]))
    return float(getattr(np, f"nan{at.value}")(values))


class DecorationConfig(ExpandableModel):
    """Shared config for every decoration.

    Mirrors ``SubplotConfig``, with one deliberate difference: ``dataset`` is
    optional, because an annotation at a fixed value reads nothing. Extra keys
    are allowed so matplotlib styling (color, linestyle, alpha, ...) flows
    straight through to the draw call via ``model_extra``.
    """

    model_config = ConfigDict(extra="allow")

    dataset: str | None = None
    var: str | None = None
    x: str | None = None
    time: str | None = None
    dim_reduce: dict[str, str | dict] | None = None
    unit: str | None = None
    label: str | None = None


class LineConfig(DecorationConfig):
    """A straight reference line, at a fixed value or a statistic of the data.

    ``at`` expands: ``at: [50, mean, p95]`` is three lines sharing the block's
    styling, fanned out at render time. ``label`` may reference the position it
    was expanded to — ``label: "Norma {at}"`` — so the legend names each line
    rather than repeating one entry.
    """

    expands = ("at",)

    at: float | ReferenceEnum | str | list[float | ReferenceEnum | str] = (
        ReferenceEnum.mean
    )

    @field_validator("at", mode="before")
    @classmethod
    def _prefer_statistic(cls, v):
        """Read a string as a named statistic first, a date second.

        Without this the smart union matches ``"mean"`` as a plain ``str`` —
        the date branch — and the enum is never reached.
        """

        def one(item):
            if isinstance(item, str):
                try:
                    return ReferenceEnum(item)
                except ValueError:
                    return item
            return item

        return [one(i) for i in v] if isinstance(v, list) else one(v)

    @model_validator(mode="after")
    def _check_statistics_have_data(self):
        """A computed position needs something to compute it from."""
        if self.dataset is not None:
            return self
        positions = self.at if isinstance(self.at, list) else [self.at]
        computed = sorted(
            {a.value for a in positions if isinstance(a, ReferenceEnum)}
        )
        if computed:
            raise ValueError(
                f"{self.type!r} decoration: {computed} are statistics of the data, "
                "so it needs a 'dataset'. A fixed numeric 'at' does not."
            )
        return self


class Line(Decorator):
    """Shared styling for the straight reference lines.

    Always built from an expanded config, so ``at`` is a single position here:
    one ``Line`` is one line.
    """

    @property
    def wants_legend(self) -> bool:
        """Only a labelled line belongs in the legend."""
        return self.decoration_config.label is not None

    def _style(self) -> dict:
        """Matplotlib kwargs, carrying the label only when there is one."""
        style = dict(self.style)
        if self.decoration_config.label is not None:
            style["label"] = self.decoration_config.label
        return style


class HLineConfig(LineConfig):
    """A horizontal line at a value."""

    type: Literal["hline", "threshold"]


class HLine(Line):
    """Decoration: a horizontal line across the axes.

    A regulatory norm written down as ``at: 50``, or a statistic of the data
    such as ``at: p95``.
    """

    config = HLineConfig
    aliases = ["hline", "threshold"]

    def draw(self, ax, data):
        """Draw a horizontal line at the resolved value."""
        value = _reference_value(data, self.decoration_config.at)
        return ax.axhline(value, **self._style())


class VLineConfig(LineConfig):
    """A vertical line at a position along the x axis."""

    type: Literal["vline", "marker"]

    @model_validator(mode="after")
    def _check_argextremes_have_coord(self):
        """argmax/argmin report a position, so they need the coordinate."""
        extremes = {ReferenceEnum.argmax, ReferenceEnum.argmin}
        positions = self.at if isinstance(self.at, list) else [self.at]
        if self.x is None and any(a in extremes for a in positions):
            raise ValueError(
                f"{self.type!r} decoration uses argmax/argmin, which report where "
                "the extreme occurs, so it needs 'x' to name that coordinate."
            )
        return self


class VLine(Line):
    """Decoration: a vertical line across the axes.

    A date written down as ``at: "15/6/2021"``, or the moment of an extreme
    with ``at: argmax``.
    """

    config = VLineConfig
    aliases = ["vline", "marker"]

    def draw(self, ax, data):
        """Draw a vertical line at the resolved position."""
        cfg = self.decoration_config
        value = _reference_value(data, cfg.at, coord=cfg.x)
        return ax.axvline(value, **self._style())
