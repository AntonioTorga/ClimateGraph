"""Geographic maths on coordinate arrays.

Grid geometry and map extents, kept apart from the drawing code that uses
them.
"""

import numpy as np

EARTH_RADIUS_M = 6_371_000.0


def step_metres(lon: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Metres per index step along each array axis of a 2-D lon/lat grid.

    Spacing is read off the coordinates cell by cell, with the equirectangular
    approximation, so a curvilinear grid works: there is no single spacing
    along an axis when a degree of longitude shrinks with latitude and both
    coordinates vary along both axes.

    The result is *along-grid*, not true east/north. On a rotated grid the
    array axes are tilted relative to the meridians and this does not correct
    for it — a few degrees over a regional domain.

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
    ex = EARTH_RADIUS_M * np.deg2rad(np.hypot(dlon_dx * coslat, dlat_dx))
    ey = EARTH_RADIUS_M * np.deg2rad(np.hypot(dlon_dy * coslat, dlat_dy))
    return ex, ey


def pad_extent(
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
    padding: float,
) -> tuple[float, float, float, float]:
    """Grow a map extent outward by ``padding``, a fraction of each axis span.

    Keeps auto-computed bounds from clipping markers on the edge. A zero-width
    span — a single point — pads by a fixed half degree so ``set_extent`` stays
    valid.

    Parameters
    ----------
    lon_min, lon_max, lat_min, lat_max : float
        The extent to grow, in degrees.
    padding : float
        Fraction of each span to add on both sides.

    Returns
    -------
    tuple[float, float, float, float]
        The padded ``(lon_min, lon_max, lat_min, lat_max)``.
    """
    lon_span = lon_max - lon_min
    lat_span = lat_max - lat_min
    lon_pad = lon_span * padding if lon_span else 0.5
    lat_pad = lat_span * padding if lat_span else 0.5
    return (
        lon_min - lon_pad,
        lon_max + lon_pad,
        lat_min - lat_pad,
        lat_max + lat_pad,
    )
