from typing import List
from pathlib import Path
import logging
import cartopy.crs as ccrs
import re
from dateutil import parser
import glob
from enum import Enum
import numpy as np
import datetime
from typing import Tuple

logging.basicConfig(level=logging.INFO)

CRS_TYPES = {"platecarree": ccrs.PlateCarree}
TIME_INTERVAL_FORMAT = r"^(.+?)\s*(?:-|to)\s*(.+)$"  # Accepts "date - date" or "date to date" and a date should be in dayfirst format.


class TimestepEnum(str, Enum):
    """TimestepEnum Enum used for timestep handling. Keeps consistent timestep values."""

    business_day = "B"
    calendar_day = "D"
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


class ReductionMethodEnum(str, Enum):
    """ReductionMethodEnum Enum used for Reduction Method handling. Keeps consistent Reduction methods values."""

    def __new__(cls, value, func):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.func = func
        return obj

    mean = ("mean", np.nanmean)
    min = ("min", np.nanmin)
    max = ("max", np.nanmax)


class CRSEnum(str, Enum):
    """CRSEnum Enum used for Coordinate Reference System handling. Keeps consistent CRS values."""

    def __new__(cls, value, crs):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.crs = crs
        return obj

    platecarree = ("platecarree", ccrs.PlateCarree)


def manage_path(paths: str | Path | List[str] | List[Path]) -> List[Path]:
    """manage_path Handles paths, including lists of paths and paths with hotkeys (*,?, etc).

    Parameters
    ----------
    paths : str | Path | List[str] | List[Path]
        Path or list of paths that compose the data object.

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

        # Detect glob pattern

        matches = glob.glob(str(p))
        if not matches:  # is empty
            logging.debug(f"No files match pattern: {raw}")
        result.extend(Path(m).resolve() for m in matches if Path(m).exists())

    if not result:  # is empty
        logging.debug(f"No files exist for paths: {paths}")

    return result


def manage_time_interval(
    time_interval: str,
) -> Tuple[datetime.datetime, datetime.datetime]:
    """manage_time_interval Manages time interval strings in the TIME_INTERVAL_FORMAT.

    Parameters
    ----------
    time_interval : str
        String in TIME_INTERVAL_FORMAT

    Returns
    -------
    Tuple[datetime.datetime, datetime.datetime]
        start datetime and end datetime.

    Raises
    ------
    ValueError
        Time interval provided doesn't meet the required format.
    """
    time_interval = time_interval.strip()
    if (match := re.match(TIME_INTERVAL_FORMAT, time_interval)) is None:
        raise ValueError(
            f"String {time_interval} could not be formatted into start and end times for a time interval.\nTime interval string must meet this format: {TIME_INTERVAL_FORMAT}"
        )

    start = parser.parse(match.group(1), dayfirst=True)
    end = parser.parse(match.group(2), dayfirst=True)

    return start, end
