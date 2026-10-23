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
    """Enum used for timestep handling. Keeps consistent timestep values."""

    business_day = "B"
    daily = "D"
    weekly = "W"
    monthly = "ME"
    quarterly = "Q"
    yearly = "Y"
    hourly = "h"
    minutely = "min"
    secondly = "s"
    milliseconds = "ms"
    microseconds = "us"
    nanoseconds = "ns"


class TimeBucketEnum(str, Enum):
    """Enum used for timestep handling. Keeps consistent timestep values."""

    minute = "minute"
    hour = "hour"
    day = "day"
    season = "season"
    weekly = "week"
    monthly = "quarter"


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


class ExpandableModel(BaseModel):
    """A config whose expanding fields fan out into sibling copies.

    Several blocks of a control file mean "do this once per value": a plot's
    ``time``, ``domains`` and ``vars``, take the product of the
    expanding fields and emit a copy per point — so they share this mechanism
    rather than being hand-written per block.

    An expanded copy stands for **exactly one** output, and its axis fields
    hold a single value rather than a one-element container. That is
    deliberate: a collection that happened to be length one would let the loops
    downstream keep running unchanged, leaving the fan-out in two places at
    once. Code consuming an expanded config should have no loop left to run.
    Because an axis field ends up holding a single value.
    """

    expands: ClassVar[tuple[str, ...]] = ()

    def expansion_values(self, field: str) -> list:
        """The per-copy values for ``field``, one per sibling.

        A list contributes its items. A mapping contributes one-entry slices
        rather than bare keys — not to preserve its shape, but because a
        ``vars: {PM25: "ug/m**3"}`` block is a name-to-unit map and the unit
        has nowhere else to live; ``expansion_token`` recovers the name for
        labelling. Anything else contributes itself.

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
