"""The maths behind a figure.

Histogram geometry and the choice of bin boundaries, kept apart from the
primitives that draw them.
"""

import numpy as np
from matplotlib.ticker import MaxNLocator

from ClimateGraph.utils.general_utils import ReductionMethodEnum


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
