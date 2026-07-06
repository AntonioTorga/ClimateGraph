from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import geopandas as gpd
import regionmask
import shapely.geometry as gm
from pydantic import BaseModel

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
