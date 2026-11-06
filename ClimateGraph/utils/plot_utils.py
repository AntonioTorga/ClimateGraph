"""The maths behind a figure, and how one gets named.

Histogram geometry, the choice of bin boundaries, and output naming — kept
apart from the primitives that draw and the plots that write.
"""

from pathlib import Path
from string import Formatter

import numpy as np
from matplotlib.ticker import MaxNLocator

from ClimateGraph.utils.general_utils import ReductionMethodEnum

# The vocabulary a `filename:` or `title:` template may reference, singular
# because that is how one figure reads.
AXIS_TOKENS = {"time": "time", "domains": "domain", "vars": "var"}


def unknown_tokens(template: str) -> list[str]:
    """Token names a template references that no figure can supply.

    Checked at config time, so a typo is an error naming the vocabulary
    rather than a traceback part-way through a run.

    Parameters
    ----------
    template : str
        A ``filename:`` or ``title:`` value.

    Returns
    -------
    list[str]
        The unsupported names, sorted. Empty when the template is usable.

    Raises
    ------
    ValueError
        If the template's braces are malformed.
    """
    referenced = {name for _, name, _, _ in Formatter().parse(template) if name}
    return sorted(referenced - set(AXIS_TOKENS.values()))


def compose_filename(
    template: str, tokens: dict, active: list[str], suffix: str
) -> str:
    """Name one figure so distinct contexts cannot land on one path.

    A template (anything containing ``{}`` fields) is formatted from
    ``tokens``; a plain string is kept as the stem it was written as. Either
    way every active axis the result does not already name is appended, since
    two figures differing only in that axis would otherwise overwrite.

    Parameters
    ----------
    template : str
        The user's ``filename:``, with or without ``{}`` fields.
    tokens : dict
        Token name to value, for formatting and for appending.
    active : list[str]
        Token names of the axes that fan out, i.e. contribute more than one
        value to this run. An axis with a single value needs no mention, so a
        plot that renders once gets exactly the name that was written.
    suffix : str
        Output format, appended as an extension unless already present.

    Returns
    -------
    str
        The filename, which may contain ``/`` when the template did.
    """
    referenced = {name for _, name, _, _ in Formatter().parse(template) if name}
    stem = template.format(**tokens) if referenced else template

    if Path(stem).suffix.lower() == f".{suffix}".lower():
        stem = stem[: -(len(suffix) + 1)]

    unnamed = [str(tokens[axis]) for axis in active if axis not in referenced]
    return "-".join([stem, *unnamed]) + f".{suffix}"


def nice_edges(lo: float, hi: float, count: int) -> np.ndarray:
    """At most ``count`` bins over ``[lo, hi]``, on boundaries that read well.

    Parameters
    ----------
    lo, hi : float
        Range to cover. The edges may extend past it to land on round numbers.
    count : int
        Upper bound on the number of bins.

    Returns
    -------
    np.ndarray
        Bin edges, ``[0, 1]`` when the span is empty or all-NaN so a caller
        with no data still has something to draw.
    """
    if not (np.isfinite(lo) and np.isfinite(hi)) or lo == hi:
        return np.array([0.0, 1.0])
    return MaxNLocator(nbins=count, steps=[1, 2, 2.5, 5, 10]).tick_values(lo, hi)


def bin_statistic(
    x: np.ndarray,
    y: np.ndarray,
    values: np.ndarray | None,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    statistic: ReductionMethodEnum,
    min_count: int = 1,
) -> np.ndarray:
    """Bin samples onto a 2-D grid and reduce the values in each cell.

    Parameters
    ----------
    x, y : np.ndarray
        Sample positions, flat and the same length.
    values : np.ndarray | None
        Quantity to reduce per cell. None returns the sample count instead.
    x_edges, y_edges : np.ndarray
        Bin boundaries along each axis.
    statistic : ReductionMethodEnum
        How the values in one cell collapse to a single number.
    min_count : int
        Cells holding fewer samples than this come back NaN.

    Returns
    -------
    np.ndarray
        Grid of shape ``(len(x_edges) - 1, len(y_edges) - 1)``.
    """
    finite = np.isfinite(x) & np.isfinite(y)
    if values is not None:
        finite &= np.isfinite(values)
    x, y = x[finite], y[finite]

    counts, _, _ = np.histogram2d(x, y, bins=[x_edges, y_edges])
    if values is None:
        grid = counts
    elif statistic is ReductionMethodEnum.mean:
        sums, _, _ = np.histogram2d(
            x, y, bins=[x_edges, y_edges], weights=values[finite]
        )
        with np.errstate(invalid="ignore"):
            grid = sums / counts
    else:
        grid = np.full(counts.shape, np.nan)
        ix = np.digitize(x, x_edges) - 1
        iy = np.digitize(y, y_edges) - 1
        # digitize sends a sample on the last edge one bin past the end,
        # where histogram2d counts it in the last bin.
        ix[x == x_edges[-1]] -= 1
        iy[y == y_edges[-1]] -= 1
        inside = (ix >= 0) & (ix < counts.shape[0]) & (iy >= 0) & (iy < counts.shape[1])
        ufunc = np.fmin if statistic is ReductionMethodEnum.min else np.fmax
        ufunc.at(grid, (ix[inside], iy[inside]), values[finite][inside])

    grid[counts < min_count] = np.nan
    return grid
