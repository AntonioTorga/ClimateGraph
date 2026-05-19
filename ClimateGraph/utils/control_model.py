from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from ClimateGraph.data import Data
from ClimateGraph.domain import Domain
from ClimateGraph.plot import Plot
from ClimateGraph.reader import Reader
from ClimateGraph.utils.general_utils import CRSEnum, manage_path


class AnalysisModel(BaseModel):
    """AnalysisModel Analysis block pydantic model. Just has output_path as a pathlib.Path and a debug flag.
    Doesn't allow extra parameters.
    """

    model_config = ConfigDict(extra="forbid")
    output_path: Path
    debug: bool
    workers: int | None = Field(default=None, ge=1)

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
    """VarModel Variable block pydantic model. Just has a name for the variable and pint-accepted unit.
    Doesn't allow extra parameters.

    Parameters
    ----------
    BaseModel : _type_
        _description_
    """

    model_config = ConfigDict(extra="forbid")
    name: str
    unit: str


class DataModel(BaseModel):
    """DataModel Data block pydantic model. Accepts topology and reader (they have to match).
    Also a single path or path list for the files that the Data object will represent.
    Accept vars mapping where the key is the name given to the variable for plotting names and internal reference.
    Also a Cartopy Coordinate Reference System managed by the CRSEnum from utils.general_utils
    Allows for extra parameters that get turned into reader kwargs.
    """

    model_config = ConfigDict(extra="allow")

    topology: str
    reader: str
    path: Path | list[Path]
    vars: dict[str, VarModel]
    crs: CRSEnum = Field(default=CRSEnum.platecarree)
    load_mode: Literal["safe", "unsafe"] = Field(default="safe")
    # Per-data download cache override. If unset, Parser falls back to
    # analysis.output_path/.cache/. Reader._resolve_paths is the only
    # site that consumes this; local-only readers ignore it.
    cache_dir: Path | None = Field(default=None)

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
    """ControlFile Complete Control/Configuration pydantic model. Gets the other pydantic models together."""

    analysis: AnalysisModel
    data: dict[str, DataModel]
    domains: dict[str, DomainModel] | None = Field(default=None)
    plots: dict[str, PlotModel] | None = Field(default=None)
    # stats

    @model_validator(mode="after")
    def check_plot_domain_refs(self):
        # Pre-M3 a typo in a plot's `domains:` list silently fell through
        # to the "no domain" branch and the plot rendered against full
        # data — a confusing failure mode. Catch unknown names early.
        if not self.plots:
            return self
        known = set(self.domains or {})
        for plot_name, plot_model in self.plots.items():
            refs = getattr(plot_model, "domains", None) or []
            missing = [d for d in refs if d not in known]
            if missing:
                raise ValueError(
                    f"Plot {plot_name!r} references unknown domain(s) {missing}. "
                    f"Known domains: {sorted(known) or '(none defined)'}."
                )
        return self
