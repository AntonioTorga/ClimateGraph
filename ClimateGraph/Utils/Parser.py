from pathlib import Path
from abc import abstractmethod
import json
import yaml

from data import Data, Reader
from plot import Plot

from pydantic import BaseModel, field_validator, model_validator


class PlotModel(BaseModel):
    type: str


class DataModel(BaseModel):
    name: str
    type: str
    subtype: str
    path: Path
    mapping: dict[str:str] | None = None
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
    def val_reader_type(cls, v: str):
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


class CollectionsModel(BaseModel):
    pass


class ControlFile(BaseModel):
    # domains
    data: dict[str:DataModel]
    plots: dict[str:PlotModel]
    collections: dict[str:CollectionsModel]
    # stats


class Parser:
    @staticmethod
    def parse_control(control_path: Path) -> dict[str:Data]:
        control_dict = Parser.read_control(control_path)
        ControlFile.model_validate(control_dict)

        # TODO: Here actually construct everything
        data = None
        plots = None
        collections = None

        return data, plots, collections

    @staticmethod
    def read_control(control_path: Path):
        # TODO: make this check file extension and read accordingly (json, yaml, etc)
        pass
