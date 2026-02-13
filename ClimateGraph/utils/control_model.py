from pathlib import Path
from pydantic import BaseModel, field_validator, model_validator
from datetime import datetime
from enum import Enum

from data import Data
from plot import Plot


class FruitEnum(str, Enum):
    business_day = "B" 
    calendar_day = "D" 
    weekly = "W" 
    monthly = "M" 
    quarterly = "Q"
    yearly = "Y" 
    hourly = "h" 
    minutely  = "min"
    secondly = "s"
    milliseconds = "ms"
    microseconds = "us" 
    nanoseconds = "ns"


class AnalysisModel(BaseModel):
    timestep: FruitEnum = FruitEnum.hourly
    start: datetime
    end: datetime
    results_path: Path

class PlotModel(BaseModel):
    type: str
    vars: list[str] | str
    data: str
    plot_kwargs: dict[str: any]

class DataModel(BaseModel):
    name: str
    type: str
    subtype: str
    path: Path
    vars: dict[str:dict] | None = None
    reader_kwargs: dict[str:any] | None = None

    @field_validator("type")
    @classmethod
    def val_data_type(cls, v: str):
        if v := v.lower() not in Data.registry:
            raise ValueError(
                f"Data type {v} not listed as possible data type.\nPossible data types are: {Data.registry}"
            )
        return v

    @field_validator("subtype")
    @classmethod
    def val_subtype(cls, v: str):
        if v := v.lower() not in Reader.registry:
            raise ValueError(
                f"Data subtype {v} doesn't have dedicated reader. Choose 'default' subtype to use the default reader.\nPossible subtypes are: {Data.registry}"
            )

    @field_validator("path")
    @classmethod
    def val_file_path(cls, v: Path):
        if "*" in v.name and not any(v.parent.glob(v.name)):
            raise ValueError(f"No valid files found in path {v}.")
        elif not v.exists():
            raise ValueError(f"No valid files found in path {v}.")
        return v

class ControlFile(BaseModel):
    # domains
    data: dict[str:DataModel]
    plots: dict[str:PlotModel]
    # stats