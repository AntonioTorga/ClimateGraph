from pathlib import Path
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from ClimateGraph.data import Data
from ClimateGraph.reader import Reader
from ClimateGraph.plot import Plot


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
    output_path: Path
    debug: bool

class PlotModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    vars: str | List[str]

    @field_validator("type")
    @classmethod
    def val_plot_type(cls, v: str):
        if (v := v.lower()) not in Plot.plot_functions:
            raise ValueError(
                f"Data type {v} not listed as possible data type.\nPossible data types are: {Plot.plot_functions}"
            )
        return v

class VarModel(BaseModel):
        model_config = ConfigDict(extra="forbid")

        name: str
        unit: str

class DataModel(BaseModel):
    type: str
    subtype: str
    path: Path | List[Path]
    vars: Dict[str, VarModel]
    kwargs: Dict[str, Any] | None = None

    @field_validator("type")
    @classmethod
    def val_data_type(cls, v: str):
        if (v := v.lower()) not in Data.registry:
            raise ValueError(
                f"Data type {v} not listed as possible data type.\nPossible data types are: {Data.registry}"
            )
        return v

    @field_validator("subtype")
    @classmethod
    def val_subtype(cls, v: str):
        if (v := v.lower()) not in Reader.registry:
            raise ValueError(
                f"Data subtype {v} doesn't have dedicated reader. Choose 'default' subtype to use the default reader.\nPossible subtypes are: {Data.registry}"
            )
        return v
    
    # TODO: enable this check at deployment
    # @field_validator("path")
    # @classmethod
    # def val_file_path(cls, v: Path):
    #     if "*" in v.name and not any(v.parent.glob(v.name)):
    #         raise ValueError(f"No valid files found in path {v}.")
    #     elif not v.exists():
    #         raise ValueError(f"No valid files found in path {v}.")
    #     return v

class ControlFile(BaseModel):
    # domains
    analysis: AnalysisModel
    data: Dict[str, DataModel]
    plots: Dict[str, PlotModel]
    # stats