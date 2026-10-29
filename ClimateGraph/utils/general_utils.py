"""Enums, path expansion, time parsing and config expansion.

The leaf utilities: how the control file's string values become real objects,
how paths and dates are interpreted, and how a block naming several values fans
out into one config per value.
"""

import datetime
import glob
import itertools
import logging
import re
from enum import Enum
from pathlib import Path
from typing import ClassVar

import cartopy.crs as ccrs
import numpy as np
import pandas as pd
from dateutil import parser
from pydantic import BaseModel

log = logging.getLogger(__name__)

CRS_TYPES = {"platecarree": ccrs.PlateCarree}
TIME_INTERVAL_FORMAT = r"^(.+?)\s*(?:-|to)\s*(.+)$"  # Accepts "date - date" or "date to date" and a date should be in dayfirst format.


class TimestepEnum(str, Enum):
    """Resample frequencies, as pandas offset aliases.

    ``hours`` is the span one step covers, so a timestep can be compared
    against the bucket it would be grouped into.
    """

    def __new__(cls, value, hours):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.hours = hours
        return obj

    business_day = ("B", 24)
    daily = ("D", 24)
    weekly = ("W", 168)
    monthly = ("ME", 720)
    # Period-end spellings: pandas 2.2 deprecated "Q"/"Y" and 3.0 removed them.
    quarterly = ("QE", 2160)
    yearly = ("YE", 8760)
    # Period-start spellings: label each bucket with its first instant.
    monthly_start = ("MS", 720)
    quarterly_start = ("QS", 2160)
    yearly_start = ("YS", 8760)
    hourly = ("h", 1)
    minutely = ("min", 1 / 60)
    secondly = ("s", 1 / 3600)
    milliseconds = ("ms", 1 / 3.6e6)
    microseconds = ("us", 1 / 3.6e9)
    nanoseconds = ("ns", 1 / 3.6e12)


class TimeBucketEnum(str, Enum):
    """Calendar buckets a time cycle groups by.

    The value is the xarray ``.dt`` accessor behind ``groupby("time.<x>")``,
    ``hours`` is the span one bucket covers, and ``period`` is how many
    buckets complete the enclosing cycle — what an angular axis divides by.
    """

    def __new__(cls, value, hours, period):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.hours = hours
        obj.period = period
        return obj

    #            value         hours  period
    minute = ("minute", 1 / 60, 60)
    hour = ("hour", 1, 24)
    day = ("day", 24, 31)
    dayofyear = ("dayofyear", 24, 366)
    weekday = ("weekday", 24, 7)
    week = ("week", 168, 53)
    month = ("month", 720, 12)
    quarter = ("quarter", 2160, 4)
    season = ("season", 2160, 4)


class ReductionMethodEnum(str, Enum):
    """Enum used for Reduction Method handling. Keeps consistent Reduction methods values."""

    def __new__(cls, value, func):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.func = func
        return obj

    mean = ("mean", np.nanmean)
    min = ("min", np.nanmin)
    max = ("max", np.nanmax)


class ReferenceEnum(str, Enum):
    """Statistics a reference line can be placed at, computed from the data.

    ``argmax``/``argmin`` are the odd ones out: they resolve to the *coordinate*
    at which the extreme occurs rather than the extreme itself, which is what a
    vertical line wants.
    """

    mean = "mean"
    median = "median"
    min = "min"
    max = "max"
    p10 = "p10"
    p25 = "p25"
    p75 = "p75"
    p90 = "p90"
    p95 = "p95"
    p99 = "p99"
    argmax = "argmax"
    argmin = "argmin"


class ProjectionEnum(str, Enum):
    """Axes types a composition can be drawn on.

    ``mpl`` is what ``add_subplot(projection=...)`` takes; None is matplotlib's
    default rectilinear axes.
    """

    def __new__(cls, value, mpl):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.mpl = mpl
        return obj

    rectilinear = ("rectilinear", None)
    polar = ("polar", "polar")


class CRSEnum(str, Enum):
    """Enum used for Coordinate Reference System handling. Keeps consistent CRS values."""

    def __new__(cls, value, crs):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.crs = crs
        return obj

    platecarree = ("platecarree", ccrs.PlateCarree)


def manage_path(
    paths: str | Path | list[str] | list[Path],
    sort: bool = False,
) -> list[Path]:
    """Handles paths, including lists of paths and glob patterns (``*``, ``?``).

    Parameters
    ----------
    paths : str | Path | List[str] | List[Path]
        Path or list of paths that compose the data object.
    sort : bool, optional
        When True, return paths in lexicographic order. If the post-sort
        order differs from the input order, log a warning — callers that
        concat in input order (e.g. the Reader unsafe path) will get a
        silently non-monotonic time axis if filenames don't embed a
        sortable timestamp. Default False keeps the historical
        glob/input order.

    Returns
    -------
    List[Path]
        List of existing pathlib.Path's created from the input paths.
    """
    if isinstance(paths, (str, Path)):
        paths = [paths]

    result: list[Path] = []

    for raw in paths:
        p = Path(raw) if isinstance(raw, str) else raw
        p = p.resolve() if not p.is_absolute() else p

        matches = glob.glob(str(p))
        if not matches:
            log.debug(f"No files match pattern: {raw}")
        result.extend(Path(m).resolve() for m in matches if Path(m).exists())

    if not result:
        log.debug(f"No files exist for paths: {paths}")

    if sort:
        ordered = sorted(result)
        if ordered != result:
            log.warning(
                "manage_path: input paths were not in lexicographic order; "
                "sorted automatically. Confirm filenames embed a sortable "
                "timestamp or callers that concat in input order will produce "
                "a non-monotonic time axis. First few: %s",
                [p.name for p in ordered[:3]],
            )
        result = ordered

    return result


# Coarsest-to-finest. Only resolutions coarser than "hour" expand to a full bucket
_RESOLUTION_ORDER = ("year", "month", "day", "hour", "minute", "second")
COARSE_OFFSETS = {
    "day": pd.Timedelta(days=1),
    "month": pd.DateOffset(months=1),
    "year": pd.DateOffset(years=1),
}


def _parse_with_resolution(token: str) -> tuple[pd.Timestamp, str]:
    """Parse a date token and detect its resolution.

    Parameters
    ----------
    token : str
        A single date/datetime in dayfirst format. With hours or without

    Returns
    -------
    tuple[pd.Timestamp, str]
        The floored timestamp and its resolution (one of ``_RESOLUTION_ORDER``).

    Raises
    ------
    ValueError
        If the token isn't a parseable date.
    """
    floored = parser.parse(token, dayfirst=True, default=datetime.datetime(1999, 1, 1))
    probe = parser.parse(
        token, dayfirst=True, default=datetime.datetime(2002, 7, 8, 9, 10, 11)
    )

    resolution = "year"
    for field in _RESOLUTION_ORDER:
        if getattr(floored, field) == getattr(probe, field):
            resolution = field
    return pd.Timestamp(floored), resolution


def _bucket_end(value: pd.Timestamp, resolution: str) -> pd.Timestamp:
    """End of the bucket ``value`` falls in, for its resolution.

    For coarse resolutions (day/month/year) returns the last representable
    instant of the bucket (start of the next bucket minus 1 ns), so an inclusive
    ``slice`` covers the whole day/month/year without spilling into the next.
    For hour-or-finer resolutions the value is an exact point and is returned
    unchanged.
    """
    offset = COARSE_OFFSETS.get(resolution)
    if offset is None:
        return value
    return value + offset - pd.Timedelta(1, "ns")


def manage_time_interval(
    time_interval: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Turn a time-interval string into (start, end).

    Accepts either a single date or a "start - (or to) end" range. Each endpoint is treated
    as an *interval covering its own resolution* when that resolution is coarser
    than hourly

    If the two endpoints have different resolutions, a warning is logged and each
    is expanded on its own bucket (best-effort).

    Parameters
    ----------
    time_interval : str
        A single date or a ``"start [-|to] end"`` range in dayfirst format.

    Returns
    -------
    tuple[pd.Timestamp, pd.Timestamp]
        Start (bucket start of the first endpoint) and end (bucket end of the
        last endpoint).

    Raises
    ------
    ValueError
        If an endpoint isn't a parseable date.
    """
    if time_interval is None:
        return None, None
    time_interval = time_interval.strip()

    # A separator splits a range; otherwise the whole string is a single date
    # that spans its own bucket (start_str == end_str).
    if (match := re.match(TIME_INTERVAL_FORMAT, time_interval)) is not None:
        start_str, end_str = match.group(1), match.group(2)
    else:
        start_str = end_str = time_interval

    start_val, start_res = _parse_with_resolution(start_str)
    end_val, end_res = _parse_with_resolution(end_str)

    if start_res != end_res:
        log.warning(
            "time_interval %r endpoints have different temporal resolutions "
            "(%s vs %s); expanding each on its own bucket.",
            time_interval,
            start_res,
            end_res,
        )

    return start_val, _bucket_end(end_val, end_res)


def normalize_time(time: str | list[str] | None) -> list[str | None]:
    """Coerce a plot's ``time`` field into a list of entries to
    iterate over. A single date/interval/None becomes a one-element list; a
    list passes through unchanged, fanning the plot out into one output per entry.

    Parameters
    ----------
    time : str | list[str] | None
        A single date/interval string, a list of them, or None.

    Returns
    -------
    list[str | None]
        Entries to iterate over, each independently valid for manage_time_interval.
    """
    if isinstance(time, list):
        return time
    return [time]


COMPASS_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

# Where theta zero sits on screen. matplotlib names the eight positions after
# compass points, which only reads correctly when the angle is a bearing.
THETA_POSITIONS = {"top": "N", "right": "E", "bottom": "S", "left": "W"}


def to_angular(da, coord, period, cycle=None):
    """Put a coordinate's values on an angular axis, in radians.

    Parameters
    ----------
    da : xr.DataArray
        Array to transform.
    coord : str | None
        Coordinate to convert. None, or a name the array does not carry,
        returns the array untouched.
    period : float
        How many of the coordinate's own units complete one turn.
    cycle : TimeBucketEnum | None
        Reads the cycle off a datetime coordinate first, so a timestamp
        becomes its day-of-year, hour or weekday.

    Returns
    -------
    xr.DataArray
        The array with ``coord`` replaced by radians.
    """
    if coord is None or coord not in da.coords:
        return da
    values = da[coord]
    if cycle is not None:
        values = getattr(values.dt, cycle.value)
        if values.dtype.kind not in "iuf":
            raise ValueError(
                f"cycle {cycle.value!r} is categorical, so it has no position "
                "on an angular axis. Use a numeric cycle such as 'month'."
            )
    return da.assign_coords({coord: 2 * np.pi * (values / period)})


def _tick_count(period, preferred: int = 8) -> int:
    """A tick count dividing the period, so labels land on whole units.

    Eight ticks over a period of seven would label weekdays 0, 0.875, 1.75.
    """
    if float(period).is_integer():
        divisors = [n for n in range(3, 13) if int(period) % n == 0]
        if divisors:
            return min(divisors, key=lambda n: (abs(n - preferred), -n))
    return preferred


def angular_ticks(
    period,
    count: int | None = None,
    zero: str = "E",
    direction: str = "counterclockwise",
):
    """Tick positions in radians, labelled in the coordinate's own units.

    Without this a polar axis labels itself in radians, so a wind rose reads
    ``0.785`` where it should read ``NE``.

    Compass labels need the axis to be a meteorological bearing — degrees,
    north at zero, winding clockwise. Under any other origin or winding the
    same positions fall on different bearings, so the labels stay numeric.

    Parameters
    ----------
    period : float
        Units completing one turn.
    count : int | None
        How many ticks to place. None picks a count that divides the period.
    zero : str
        Where the axes puts theta zero: ``N``, ``E``, ``S`` or ``W``.
    direction : str
        ``clockwise`` or ``counterclockwise``.

    Returns
    -------
    tuple[list[float], list[str]]
        Positions in radians, and their labels.
    """
    if count is None:
        count = _tick_count(period)
    positions = [2 * np.pi * i / count for i in range(count)]
    is_bearing = (
        period == 360
        and zero == "N"
        and direction == "clockwise"
        and count == len(COMPASS_POINTS)
    )
    if is_bearing:
        return positions, list(COMPASS_POINTS)
    step = period / count
    return positions, [f"{i * step:g}" for i in range(count)]


class ExpandableModel(BaseModel):
    """A config whose expanding fields fan out into sibling copies.

    Several control-file blocks mean "do this once per value" — a plot's
    ``time``, ``domains``, ``vars`` ... :func:`expand` takes the product of the fields named
    in ``expands`` and emits one copy per point.

    An expanded copy holds a **single value** per axis, not a one-element
    container, so code consuming one has no loop left to run. Its annotation
    has to admit that value, which is why the plot configs declare ``time``
    and ``domains`` as ``str | list[str]``.

    ``expansion_values`` and ``expansion_gate`` cover the axes that are not
    simply "the list in that field": a Points domain fans over names that are
    not a declared list, and an Attribute domain fans only when
    ``one_for_each`` is set.
    """

    expands: ClassVar[tuple[str, ...]] = ()

    def expansion_values(self, field: str) -> list:
        """The per-copy values for ``field``, one per sibling.

        A list contributes its items; anything else contributes itself. A
        mapping contributes one-entry slices, because a
        ``vars: {PM25: "ug/m**3"}`` block carries the unit alongside the name
        and ``expansion_token`` recovers the name for labelling.

        An empty collection is not an axis and passes through whole, so
        ``domains: []`` still renders once rather than zero times.

        Parameters
        ----------
        field : str
            Name of the expanding field.

        Returns
        -------
        list
            One value per sibling copy.
        """
        value = getattr(self, field, None)
        if isinstance(value, list) and value:
            return list(value)
        if isinstance(value, dict) and value:
            return [{key: item} for key, item in value.items()]
        return [value]

    @staticmethod
    def expansion_token(value):
        """The name of a slot value, for filenames and titles.

        A one-entry mapping gives up its key, and an enum its value — a bare
        ``format()`` of an enum renders ``ReferenceEnum.mean`` rather than
        ``mean``. Every other axis value is already its own name.
        """
        if isinstance(value, dict) and len(value) == 1:
            return next(iter(value))
        if isinstance(value, Enum):
            return value.value
        return value

    def expansion_gate(self, field: str) -> bool:
        """Whether ``field`` fans out at all. True unless overridden."""
        return True


def expand(model: ExpandableModel) -> list[tuple[dict, ExpandableModel]]:
    """Fan a config out into one copy per point of its expansion product.

    Parameters
    ----------
    model : ExpandableModel
        The config to expand.

    Returns
    -------
    list[tuple[dict, ExpandableModel]]
        ``(slots, copy)`` pairs. ``copy`` stands for one output, with every
        axis pinned to a single value; ``slots`` maps each axis to that value's
        name, which is what naming and templating read.

        A config with no active axes yields exactly one pair, so callers never
        have to special-case the un-expanded form.
    """
    axes = [field for field in model.expands if model.expansion_gate(field)]
    if not axes:
        return [({}, model)]

    expanded = []
    for combo in itertools.product(*(model.expansion_values(f) for f in axes)):
        update = dict(zip(axes, combo, strict=True))
        slots = {field: model.expansion_token(v) for field, v in update.items()}
        expanded.append((slots, model.model_copy(update=update)))
    return expanded
