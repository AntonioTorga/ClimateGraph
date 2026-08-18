from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import geopandas as gpd
import pandas as pd
import regionmask
import shapely.geometry as gm
from pydantic import BaseModel, model_validator

from .domain import Domain

if TYPE_CHECKING:
    from ClimateGraph.data.data import Data


class BaseDomainConfig(BaseModel):
    """BaseDomainConfig Shared config fields for every domain.

    Carries the optional spatial resample pre-step: when ``resample_to`` names
    another dataset, the domain first reprojects the incoming data onto that
    dataset's geometry, then runs its own filter over the resampled result.
    """

    resample_to: str | None = None
    """Name of another dataset to reproject onto before filtering. None = no resample."""
    radius_of_influence: int = 50000
    engine: str = "pyresample"
    engine_kwargs: dict | None = None


class AttributeConfig(BaseDomainConfig):
    """AttributeConfig Pydantic model for the Attribute domain definition in the config file."""

    type: Literal["attribute", "attr"]
    field_name: str
    field_value: Any
    one_for_each: bool = False
    """When field_value is a list and this is True, the parser expands this
    single domain block into one Attribute domain per value. When False (default),
    the set is analyzed together."""


class Attribute(Domain):
    """Attribute Domain specification by attribute in a xr.Dataset, uses Attribute==Value as a mask"""

    config = AttributeConfig
    aliases = ["attribute", "attr"]

    def _filter(self, data: "Data") -> "Data":
        """_filter Filters the data with a mask defined by a field and a field value.

        Parameters
        ----------
        data : Data
            Data to be filtered

        Returns
        -------
        Data
            Data filtered containing the attribute defined.
        """
        field_name = self.domain_config.field_name
        field_value = self.domain_config.field_value
        if isinstance(field_value, list):
            mask = data.obj[field_name].isin(field_value)
        else:
            mask = data.obj[field_name] == field_value
        result = data.copy()
        result.obj = data.obj.where(mask.compute(), drop=True)
        return result


class PolygonConfig(BaseDomainConfig):
    """PolygonConfig Pydantic model for the Polygon domain definition in the config file. The only argument is vertex which is a List of tuples representing vertices, or List of vertices (List of List of tuples)"""

    type: Literal["polygon", "poly"]
    vertex: list[tuple[float, float]] | list[list[tuple[float, float]]]


class Polygon(Domain):
    """Polygon Domain specification by polygons specified with a list of vertices, or list of list of vertices (multipolygon)"""

    config = PolygonConfig
    aliases = ["polygon", "poly"]

    def _filter(self, data: "Data") -> "Data":
        """_filter Constructs the polygons with a set of vertices and uses them to filter the data.

        Parameters
        ----------
        data : Data
            Data to be filtered by the polygons

        Returns
        -------
        Data
            Data filtered by the polygon(s)
        """
        vertex = self.domain_config.vertex
        if isinstance(vertex[0], tuple):
            vertex = [vertex]
        polygons = []

        for p in vertex:
            polygons.append(gm.Polygon(p))

        polygons = gm.MultiPolygon(polygons)
        regions = regionmask.Regions([polygons])

        # Regionmask requires "lat" and "lon"
        region_mask = regions.mask(
            data.obj.rename({"latitude": "lat", "longitude": "lon"})
        )
        region_mask = region_mask.rename({"lat": "latitude", "lon": "longitude"})

        result = data.copy()
        result.obj = data.obj.where(region_mask.notnull())
        return result


class AllConfig(BaseDomainConfig):
    """AllConfig Pydantic model for the All domain — no filtering applied."""

    type: Literal["all"]


class All(Domain):
    """All domain that returns data unchanged — explicit 'use all data' marker.

    With ``resample_to`` set it becomes a pure reprojection (resample, no filter).
    """

    config = AllConfig
    aliases = ["all"]

    def _filter(self, data: "Data") -> "Data":
        return data


class PointItem(BaseModel):
    """A single named point for an inline ``Points`` domain."""

    name: str
    lat: float
    lon: float


# Tolerated CSV header spellings for each logical column.
_POINT_COL_ALIASES = {
    "name": ("name", "site", "station", "id"),
    "lat": ("latitude", "lat", "latitud"),
    "lon": ("longitude", "lon", "longitud"),
}


class PointsConfig(BaseDomainConfig):
    """PointsConfig Resample onto a set of named points given inline or via CSV.

    The domain carries its own target geometry (the points), so ``resample_to`` is
    unused; ``radius_of_influence``/``engine`` from the base still drive the resample.
    """

    type: Literal["points", "pts"]
    path: Path | None = None
    """CSV of named points (columns: name + latitude/longitude, aliases tolerated)."""
    points: list[PointItem] | None = None
    """Inline alternative to ``path``: a list of ``{name, lat, lon}``."""
    name_col: str = "name"
    lat_col: str = "latitude"
    lon_col: str = "longitude"
    one_for_each: bool = False
    """Expand into one domain per point (named by the point) instead of one grouped
    domain over all points."""
    select_name: str | None = None
    """Internal: set by the parser on each fan-out expansion to the point to keep."""

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "PointsConfig":
        if (self.path is None) == (self.points is None):
            raise ValueError(
                "Points domain needs exactly one of 'path' (CSV) or 'points' (inline)."
            )
        return self

    def _resolve_col(self, columns, logical: str, configured: str) -> str:
        """Find the CSV column for a logical field (configured name, else an alias)."""
        lower = {c.lower(): c for c in columns}
        for candidate in (configured, *_POINT_COL_ALIASES[logical]):
            if candidate.lower() in lower:
                return lower[candidate.lower()]
        raise ValueError(
            f"Points CSV is missing a '{logical}' column "
            f"(looked for {configured!r} or {_POINT_COL_ALIASES[logical]}); "
            f"has {list(columns)}."
        )

    def resolve_points(self) -> list[tuple[str, float, float]]:
        """Return the points as ``[(name, lat, lon), ...]`` from inline or CSV."""
        if self.points is not None:
            return [(p.name, p.lat, p.lon) for p in self.points]
        df = pd.read_csv(self.path)
        name_c = self._resolve_col(df.columns, "name", self.name_col)
        lat_c = self._resolve_col(df.columns, "lat", self.lat_col)
        lon_c = self._resolve_col(df.columns, "lon", self.lon_col)
        return [
            (str(r[name_c]), float(r[lat_c]), float(r[lon_c])) for _, r in df.iterrows()
        ]


class Points(Domain):
    """Points domain: resample any dataset onto a fixed set of named points.

    The parser builds a ``PointSurface`` target from the config's points and injects
    it as the resample target, so the base ``apply`` template reprojects onto the
    points and then ``_filter`` runs. Grouped (``select_name`` None) keeps every
    point; a fan-out expansion selects its single named point.
    """

    config = PointsConfig
    aliases = ["points", "pts"]

    def _filter(self, data: "Data") -> "Data":
        sel = self.domain_config.select_name
        if sel is None:
            return data
        result = data.copy()
        result.obj = data.obj.sel(site=[sel])
        return result


class ShapefileConfig(BaseDomainConfig):
    """ShapefileConfig Pydantic model for the Polygon domain definition in the config file. Receives a local path to the shapefile, and a value for filtering."""

    type: Literal["shapefile", "shp"]
    path: Path
    field_value: Any


class Shapefile(Domain):
    """Shapefile domain defined by an imported shapefile and a field value inside of it."""

    config = ShapefileConfig
    aliases = ["shapefile", "shp"]

    def _filter(self, data: "Data") -> "Data":
        """_filter Loads shapefile and constructs a regionmask.regionmask with it. Applies the mask over the provided data.

        Parameters
        ----------
        data : Data
            Data to be filtered by the shapefile.

        Returns
        -------
        Data
            Data filtered by the shapefile
        """
        path = self.domain_config.path
        field_value = self.domain_config.field_value

        regions = regionmask.from_geopandas(gpd.read_file(path))

        region_mask = regions.mask(
            data.obj.rename({"latitude": "lat", "longitude": "lon"})
        )
        region_mask = region_mask.rename({"lat": "latitude", "lon": "longitude"})

        result = data.copy()
        result.obj = data.obj.where(region_mask == field_value)
        return result
