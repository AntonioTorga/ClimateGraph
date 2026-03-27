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
    type: Literal["attribute", "attr"]
    field_name: str
    field_value: Any

class Attribute(Domain):
    config = AttributeConfig
    aliases = ["attribute", "attr"]

    def apply(self, data: xr.Dataset|xr.DataArray):
        field_name = self.domain_config.field_name
        field_value = self.domain_config.field_value
        return data.where((data[field_name]==field_value).compute(), drop=True)
    
class PolygonConfig(BaseModel):
    type: Literal["polygon", "poly"]
    vertex : List[Tuple[float, float]] | List[List[Tuple[float, float]]]

class Polygon(Domain):
    config = PolygonConfig
    aliases = ["polygon", "poly"]

    def apply(self, data: xr.Dataset|xr.DataArray):
        vertex = self.domain_config.vertex
        if isinstance(vertex[0], tuple): vertex = [vertex]
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
    type: Literal["shapefile", "shp"]
    path : Path
    field_value: Any

class Shapefile(Domain):
    config = ShapefileConfig
    aliases = ["shapefile", "shp"]

    def apply(self, data: xr.Dataset|xr.DataArray):    
        path = self.domain_config.path
        field_value = self.domain_config.field_value

        regions = regionmask.from_geopandas(gpd.read_file(path))
        
        region_mask = regions.mask(data.rename({"latitude": "lat", "longitude": "lon"}))
        region_mask = region_mask.rename({"lat": "latitude", "lon": "longitude"})

        masked_data = data.where(region_mask == field_value)
        return masked_data
