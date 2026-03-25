from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, Field
from typing import Dict, List, Optional


from ClimateGraph.data import Data
from ClimateGraph.reader import Reader
from ClimateGraph.plot import Plot
from ClimateGraph.domain import Domain
from ClimateGraph.utils.general_utils import manage_path, manage_crs, CRSEnum


class AnalysisModel(BaseModel):
    output_path: Path
    debug: bool

    @field_validator("output_path")
    @classmethod
    def val_output_path(cls, v: Path):
        v = v.resolve()
        if not v.exists():
            v.mkdir(parents=True)
        return v

PlotModel = Plot.build_config_union()
DomainModel = Domain.build_config_union()

class VarModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    unit: str

class DataModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    topology: str
    reader: str
    path: Path | List[Path]
    vars: Dict[str, VarModel]
    crs: CRSEnum = Field(default=CRSEnum.platecarree)

    @field_validator("topology")
    @classmethod
    def val_data_topology(cls, v: str):
        if not Data.check_topology_type(v):
            raise ValueError(
                f"Topology type {v} not listed as possible data type.\nPossible data types are: {list(Data.registry.keys())}"
            )
        return v

    @field_validator("path")
    @classmethod
    def val_file_path(cls, v):
        path = manage_path(v)
        if not path:
            raise ValueError(f"No files found for path {v}")
        return path

    @model_validator(mode="after")
    def check_type_and_subtype_are_consistent(self):
        if not (Reader.check_reader_type(self.topology, self.reader)):
            raise ValueError(
                f"Topology {self.topology} doesn't have reader of type {self.reader}."
            )
        return self


class ControlFile(BaseModel):
    # domains
    analysis: AnalysisModel
    domains: Dict[str, DomainModel]
    data: Dict[str, DataModel]
    plots: Dict[str, PlotModel]
    # stats
