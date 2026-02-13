from pathlib import Path
from pydantic import BaseModel, field_validator, model_validator

from data import Data, Reader
from plot import Plot


class CollectionModel(BaseModel):
    main_dataset: str
    datasets: list[str]

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