from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Tuple, Any
import numpy as np
import regionmask
import geopandas as gpd
import shapely.geometry as gm
from pathlib import Path
import xarray as xr

from .domain import Domain


class AttributeConfig(BaseModel):
    """AttributeConfig Pydantic model for the Attribute domain definition in the config file."""

    type: Literal["attribute", "attr"]
    field_name: str
    field_value: Any


class Attribute(Domain):
    """Attribute Domain specification by attribute in a xr.Dataset, uses Attribute==Value as a mask"""

    config = AttributeConfig
    aliases = ["attribute", "attr"]

    def apply(self, data: xr.Dataset | xr.DataArray):
        """apply Filters the data with a mask defined by a field and a field value.

        Parameters
        ----------
        data : xr.Dataset | xr.DataArray
            Data to be filtered

        Returns
        -------
        xr.Dataset|xr.DataArray
            Data filtered containing the attributed defined.
        """
        field_name = self.domain_config.field_name
        field_value = self.domain_config.field_value
        return data.where((data[field_name] == field_value).compute(), drop=True)


class PolygonConfig(BaseModel):
    """PolygonConfig Pydantic model for the Polygon domain definition in the config file. The only argument is vertex which is a List of tuples representing vertices, or List of vertices (List of List of tuples)"""

    type: Literal["polygon", "poly"]
    vertex: List[Tuple[float, float]] | List[List[Tuple[float, float]]]


class Polygon(Domain):
    """Polygon Domain specification by polygons specified with a list of vertices, or list of list of vertices (multipolygon)"""

    config = PolygonConfig
    aliases = ["polygon", "poly"]

    def apply(self, data: xr.Dataset | xr.DataArray):
        """apply Constructs the polygons with a set of vertices and uses them to filter the data.

        Parameters
        ----------
        data : xr.Dataset | xr.DataArray
            Data to be filtered by the polygons

        Returns
        -------
        xr.Dataset|xr.DataArray
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
        region_mask = regions.mask(data.rename({"latitude": "lat", "longitude": "lon"}))
        region_mask = region_mask.rename({"lat": "latitude", "lon": "longitude"})

        masked_data = data.where(region_mask.notnull())

        return masked_data


class ShapefileConfig(BaseModel):
    """ShapefileConfig Pydantic model for the Polygon domain definition in the config file. Receives a local path to the shapefile, and a value for filtering."""

    type: Literal["shapefile", "shp"]
    path: Path
    field_value: Any


class Shapefile(Domain):
    """Shapefile domain defined by an imported shapefile and a field value inside of it."""

    config = ShapefileConfig
    aliases = ["shapefile", "shp"]

    def apply(self, data: xr.Dataset | xr.DataArray):
        """apply Loads shapefile and constructs a regionmask.regionmask with it. Applies the mask over the provided data.

        Parameters
        ----------
        data : xr.Dataset | xr.DataArray
            Data to be filtered by the shapefile.

        Returns
        -------
        xr.Dataset | xr.DataArray
            Data filtered by the shapefile
        """
        path = self.domain_config.path
        field_value = self.domain_config.field_value

        regions = regionmask.from_geopandas(gpd.read_file(path))

        region_mask = regions.mask(data.rename({"latitude": "lat", "longitude": "lon"}))
        region_mask = region_mask.rename({"lat": "latitude", "lon": "longitude"})

        masked_data = data.where(region_mask == field_value)
        return masked_data
