"""Pydantic control file model.

Pydantic models for every block of a control file, composed by
:class:`ControlFile`. Each model carries the checks that belong to it, and
``ControlFile`` carries the ones that do consistency checks between blocks

The plot and domain schemas are not written here: they are assembled at import
time from the abstract class registry.
"""

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

_DATASET_REF_FIELDS = ("base", "superposed", "data")


class AnalysisModel(BaseModel):
    """The ``analysis`` block: run-scoped settings.

    Forbids extra keys, so a misspelled setting here is an error rather than a
    silent no-op.
    """

    model_config = ConfigDict(extra="forbid")
    output_path: Path
    debug: bool = Field(default=False)
    workers: int | None = Field(default=None, ge=1)

    @field_validator("output_path")
    @classmethod
    def val_output_path(cls, v: Path):
        """Resolve the output path, creating the directory if it does not exist."""
        v = v.resolve()
        if not v.exists():
            v.mkdir(parents=True)
        return v


PlotModel = Plot.build_config_union()
DomainModel = Domain.build_config_union()


class VarModel(BaseModel):
    """One entry of a dataset's ``vars`` mapping.

    Carries the file-native name to rename from, a pint unit enabling conversion
    at plot time, and arithmetic applied at read time. Forbids extra keys.
    """

    model_config = ConfigDict(extra="forbid")
    # Optional: the file-native name to rename from. A composed variable (one
    # built purely from others via `operation`) has no file name and omits it.
    name: str | None = Field(default=None)
    # Optional: without a unit the variable is left as-is (no conversion) and
    # plot labels omit the unit. Provide it to enable pint unit conversion.
    unit: str | None = Field(default=None)
    # Optional arithmetic applied at reader time. May reference the variable's
    # own file data (`x`) and other base variables by their canonical name, to
    # transform units or compose a new variable. See dataset_utils.apply_operation.
    operation: str | None = Field(default=None)

    @model_validator(mode="after")
    def check_name_or_operation(self):
        """Require a ``name``, an ``operation``, or both."""
        if self.name is None and self.operation is None:
            raise ValueError(
                "a variable must declare a 'name' (read from the file) and/or an "
                "'operation' (composed from other variables); got neither."
            )
        return self


class DataModel(BaseModel):
    """One entry of the ``data`` block: a dataset declaration.

    The topology and the reader must be consistent — a reader is registered
    against the topology it can read. Variable names declared here are the
    handles used everywhere else in the control file.

    Allows extra keys on purpose: anything unrecognised is forwarded to the
    reader as a keyword argument, so reader-specific options need no schema
    change here.
    """

    model_config = ConfigDict(extra="allow")

    topology: str
    reader: str
    path: Path | list[Path]
    # Optional. A dict maps user-facing names to {name, unit, operation} (units
    # optional); a plain list[str] selects file-native names with no units; None
    # (omitted) keeps every variable in the file under its file-native name.
    vars: dict[str, VarModel] | list[str] | None = Field(default=None)
    crs: CRSEnum = Field(default=CRSEnum.platecarree)
    load_mode: Literal["safe", "unsafe"] = Field(default="safe")
    # Per-data download cache override. If unset, Parser falls back to
    # analysis.output_path/.cache/. Reader._resolve_paths is the only
    # site that consumes this; local-only readers ignore it.
    cache_dir: Path | None = Field(default=None)
    # Optional destination for the fully-processed dataset. When set,

    save_to: Path | None = Field(default=None)

    @field_validator("topology")
    @classmethod
    def val_data_topology(cls, v: str):
        """Check the topology is one the Data registry knows."""
        if not Data.check_topology_type(v):
            raise ValueError(
                f"Topology type {v} not listed as possible data type.\nPossible data types are: {list(Data.registry.keys())}"
            )
        return v

    @field_validator("path")
    @classmethod
    def val_file_path(cls, v):
        """Expand the path or glob and require it to match at least one file."""
        path = manage_path(v)
        if not path:
            raise ValueError(f"No files found for path {v}")
        return path

    @field_validator("save_to")
    @classmethod
    def val_save_to(cls, v: Path | None):
        """Require ``save_to`` to name a NetCDF file rather than a directory."""
        # fail at check time for save_to argument
        if v is None:
            return v
        if v.is_dir() or v.suffix.lower() not in Reader.netcdf_suffixes:
            raise ValueError(
                f"save_to must be an exact NetCDF file path "
                f"(one of {Reader.netcdf_suffixes}); got {v!r}."
            )
        return v

    @model_validator(mode="after")
    def check_type_and_subtype_are_consistent(self):
        """Check the reader is registered against the declared topology."""
        if not (Reader.check_reader_type(self.topology, self.reader)):
            raise ValueError(
                f"Topology {self.topology} doesn't have reader of type {self.reader}."
            )
        return self


class ControlFile(BaseModel):
    """The whole control file.

    Composes the block models and performs inter block checks.
    """

    analysis: AnalysisModel
    data: dict[str, DataModel]
    domains: dict[str, DomainModel] | None = Field(default=None)
    plots: dict[str, PlotModel] | None = Field(default=None)
    # stats

    @model_validator(mode="after")
    def check_plot_domain_refs(self):
        """Check every domain a plot references is defined.

        Without this a typo fell through to the "no domain" branch and the plot
        silently rendered against the full dataset.
        """
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

    @model_validator(mode="after")
    def check_plot_var_refs(self):
        """Catch plot var names that can't resolve in a referenced dataset.

        With canonical names now optional, if vars was set then performs a check
        against it. If not it ignores and assumes you are referencing a real name in the ds.
        If mistaken a KeyError will occur at runtime.
        """
        if not self.plots:
            return self
        for plot_name, plot_model in self.plots.items():
            plot_vars = _plot_var_names(getattr(plot_model, "vars", None))
            if not plot_vars:
                continue
            for ds_name in _referenced_datasets(plot_model, _DATASET_REF_FIELDS):
                data_model = self.data.get(ds_name)
                if data_model is None:
                    continue
                declared = _declared_var_names(data_model.vars)
                if declared is None:
                    continue  # vars omitted — defer to runtime
                missing = sorted(plot_vars - declared)
                if missing:
                    raise ValueError(
                        f"Plot {plot_name!r} references variable(s) {missing} "
                        f"not declared in dataset {ds_name!r}. "
                        f"Declared vars: {sorted(declared) or '(none)'}."
                    )
        return self

    @model_validator(mode="after")
    def check_custom_subplot_var_refs(self):
        """Catch ``type: custom`` subplot var names that can't resolve.

        ``check_plot_var_refs`` equivalent for subplots. Checks that every var referenced
        exists in the target Dataset (be it specific to the subplot or at custom plot level)
        If dataset vars are not defined, could lead to a KeyError in get_vars
        """
        if not self.plots:
            return self
        for plot_name, plot_model in self.plots.items():
            subplots = getattr(plot_model, "subplots", None)
            if not subplots:
                continue
            plot_vars = _plot_var_names(getattr(plot_model, "vars", None))
            for subplot in subplots:
                ds_name = getattr(subplot, "dataset", None)
                data_model = self.data.get(ds_name) if ds_name else None
                if data_model is None:
                    continue
                declared = _declared_var_names(data_model.vars)
                if declared is None:
                    continue  # vars omitted — defer to runtime
                subplot_var = getattr(subplot, "var", None)
                check_vars = {subplot_var} if subplot_var is not None else plot_vars
                missing = sorted(v for v in check_vars if v not in declared)
                if missing:
                    raise ValueError(
                        f"Plot {plot_name!r} subplot references variable(s) "
                        f"{missing} not declared in dataset {ds_name!r}. "
                        f"Declared vars: {sorted(declared) or '(none)'}."
                    )
        return self


def _plot_var_names(vars: str | list[str] | dict[str, str] | None) -> set[str]:
    """Variable names a plot references, regardless of the form ``vars`` took."""
    if vars is None:
        return set()
    if isinstance(vars, str):
        return {vars}
    if isinstance(vars, dict):
        return set(vars.keys())
    return set(vars)


def _declared_var_names(
    vars: dict[str, VarModel] | list[str] | None,
) -> set[str] | None:
    """Names a dataset exposes, or ``None`` when vars was omitted (unknowable)."""
    if isinstance(vars, dict):
        return set(vars.keys())
    if isinstance(vars, list):
        return set(vars)
    return None


def _referenced_datasets(plot_model, fields: tuple[str, ...]) -> set[str]:
    """Collect data-block names a plot points at across its reference fields."""
    names: set[str] = set()
    for field in fields:
        value = getattr(plot_model, field, None)
        if isinstance(value, str):
            names.add(value)
        elif isinstance(value, list):
            names.update(v for v in value if isinstance(v, str))
    return names
