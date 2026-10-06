from pathlib import Path

import pytest
from pydantic import ValidationError

from ClimateGraph.utils.control_model import (
    AnalysisModel,
    ControlFile,
    DataModel,
    VarModel,
)


def _make_data_file(tmp_path: Path, name: str = "x.nc") -> Path:
    """Materialise an empty file so the path validator passes."""
    p = tmp_path / name
    p.write_bytes(b"")
    return p


@pytest.fixture
def base_data_block(tmp_path):
    _make_data_file(tmp_path)
    return {
        "topology": "RegularGrid",
        "reader": "wrf",
        "path": str(tmp_path / "x.nc"),
        "vars": {"Temperatura": {"name": "T2", "unit": "kelvin"}},
    }


class TestAnalysisModel:
    def test_creates_output_dir_if_missing(self, tmp_path):
        target = tmp_path / "results" / "nested"
        model = AnalysisModel(output_path=str(target), debug=True)
        assert model.output_path.exists()
        assert model.output_path == target.resolve()

    def test_forbids_extra_keys(self, tmp_path):
        with pytest.raises(ValidationError):
            AnalysisModel(output_path=str(tmp_path), debug=True, unknown_field="oops")


class TestVarModel:
    def test_minimal(self):
        v = VarModel(name="T2", unit="kelvin")
        assert v.name == "T2"

    def test_forbids_extra(self):
        with pytest.raises(ValidationError):
            VarModel(name="T2", unit="kelvin", source="WRF")

    def test_operation_only_without_name(self):
        # A composed variable has no file-native name.
        v = VarModel(operation="A + B")
        assert v.name is None
        assert v.operation == "A + B"

    def test_requires_name_or_operation(self):
        with pytest.raises(ValidationError, match=r"name.*and/or.*operation"):
            VarModel(unit="kelvin")


class TestDataModel:
    def test_happy_path(self, base_data_block):
        model = DataModel.model_validate(base_data_block)
        assert model.topology == "RegularGrid"
        assert model.reader == "wrf"

    def test_unknown_topology_rejected(self, base_data_block):
        base_data_block["topology"] = "WhatIsThis"
        with pytest.raises(ValidationError):
            DataModel.model_validate(base_data_block)

    def test_reader_mismatch_rejected(self, base_data_block):
        # DMC is a PointSurface reader, not RegularGrid.
        base_data_block["reader"] = "dmc"
        with pytest.raises(ValidationError):
            DataModel.model_validate(base_data_block)

    def test_missing_files_rejected(self, base_data_block, tmp_path):
        base_data_block["path"] = str(tmp_path / "no-such-file.nc")
        with pytest.raises(ValidationError):
            DataModel.model_validate(base_data_block)

    def test_extra_kwargs_pass_through_as_reader_kwargs(self, base_data_block):
        base_data_block["custom_kwarg"] = 42
        model = DataModel.model_validate(base_data_block)
        assert model.model_extra == {"custom_kwarg": 42}

    def test_save_to_accepts_netcdf_file(self, base_data_block, tmp_path):
        base_data_block["save_to"] = str(tmp_path / "out.nc")
        model = DataModel.model_validate(base_data_block)
        assert model.save_to == tmp_path / "out.nc"

    def test_save_to_directory_rejected(self, base_data_block, tmp_path):
        base_data_block["save_to"] = str(tmp_path)
        with pytest.raises(ValidationError, match="exact NetCDF file path"):
            DataModel.model_validate(base_data_block)

    def test_save_to_non_netcdf_suffix_rejected(self, base_data_block, tmp_path):
        base_data_block["save_to"] = str(tmp_path / "out.txt")
        with pytest.raises(ValidationError, match="exact NetCDF file path"):
            DataModel.model_validate(base_data_block)

    def test_vars_optional_when_omitted(self, base_data_block):
        base_data_block.pop("vars")
        model = DataModel.model_validate(base_data_block)
        assert model.vars is None

    def test_vars_accepts_bare_list(self, base_data_block):
        base_data_block["vars"] = ["T2", "PSFC"]
        model = DataModel.model_validate(base_data_block)
        assert model.vars == ["T2", "PSFC"]


class TestControlFile:
    def test_full_minimal_config(self, tmp_path, base_data_block):
        cfg = {
            "analysis": {"output_path": str(tmp_path / "out"), "debug": False},
            "data": {"WRF": base_data_block},
        }
        model = ControlFile.model_validate(cfg)
        assert model.analysis.debug is False
        assert "WRF" in model.data
        assert model.plots is None
        assert model.domains is None

    def test_plot_referencing_unknown_domain_is_rejected(
        self, tmp_path, base_data_block
    ):
        cfg = {
            "analysis": {"output_path": str(tmp_path / "out"), "debug": False},
            "data": {"WRF": base_data_block},
            "domains": {
                "RM": {"type": "attribute", "field_name": "region", "field_value": 13},
            },
            "plots": {
                "TS": {
                    "type": "timeseries",
                    "vars": "Temperatura",
                    "domains": ["RM", "does_not_exist"],
                    "data": "WRF",
                },
            },
        }
        with pytest.raises(ValidationError, match="unknown domain"):
            ControlFile.model_validate(cfg)

    def test_plot_with_known_domain_passes(self, tmp_path, base_data_block):
        cfg = {
            "analysis": {"output_path": str(tmp_path / "out"), "debug": False},
            "data": {"WRF": base_data_block},
            "domains": {
                "RM": {"type": "attribute", "field_name": "region", "field_value": 13},
            },
            "plots": {
                "TS": {
                    "type": "timeseries",
                    "vars": "Temperatura",
                    "domains": ["RM"],
                    "data": "WRF",
                },
            },
        }
        model = ControlFile.model_validate(cfg)
        assert "TS" in model.plots

    def test_plot_referencing_undeclared_var_rejected(self, tmp_path, base_data_block):
        # WRF declares only "Temperatura"; the plot asks for "Presion".
        cfg = {
            "analysis": {"output_path": str(tmp_path / "out"), "debug": False},
            "data": {"WRF": base_data_block},
            "plots": {
                "TS": {"type": "timeseries", "vars": "Presion", "data": "WRF"},
            },
        }
        with pytest.raises(ValidationError, match="not declared in dataset"):
            ControlFile.model_validate(cfg)

    def test_plot_var_ref_deferred_when_dataset_vars_omitted(
        self, tmp_path, base_data_block
    ):
        # With vars omitted the exposed names are unknown until load, so the
        # var-ref check defers (no error here) to the runtime KeyError.
        base_data_block.pop("vars")
        cfg = {
            "analysis": {"output_path": str(tmp_path / "out"), "debug": False},
            "data": {"WRF": base_data_block},
            "plots": {
                "TS": {"type": "timeseries", "vars": "T2", "data": "WRF"},
            },
        }
        model = ControlFile.model_validate(cfg)
        assert "TS" in model.plots

    def test_custom_subplot_undeclared_var_rejected(self, tmp_path, base_data_block):
        # Per-subplot var checked against that subplot's own dataset.
        cfg = {
            "analysis": {"output_path": str(tmp_path / "out"), "debug": False},
            "data": {"WRF": base_data_block},
            "plots": {
                "C": {
                    "type": "custom",
                    "subplots": [
                        {
                            "type": "series",
                            "dataset": "WRF",
                            "x": "time",
                            "var": "Nope",
                        }
                    ],
                },
            },
        }
        with pytest.raises(ValidationError, match="not declared in dataset"):
            ControlFile.model_validate(cfg)

    def test_custom_plot_level_var_checked_per_subplot(self, tmp_path, base_data_block):
        # Plot-level vars must resolve in every subplot's dataset.
        cfg = {
            "analysis": {"output_path": str(tmp_path / "out"), "debug": False},
            "data": {"WRF": base_data_block},
            "plots": {
                "C": {
                    "type": "custom",
                    "vars": ["Nope"],
                    "subplots": [
                        {
                            "type": "contourf",
                            "dataset": "WRF",
                            "x": "longitude",
                            "y": "latitude",
                        }
                    ],
                },
            },
        }
        with pytest.raises(ValidationError, match="not declared in dataset"):
            ControlFile.model_validate(cfg)

    def test_custom_subplot_known_var_passes(self, tmp_path, base_data_block):
        cfg = {
            "analysis": {"output_path": str(tmp_path / "out"), "debug": False},
            "data": {"WRF": base_data_block},
            "plots": {
                "C": {
                    "type": "custom",
                    "subplots": [
                        {
                            "type": "series",
                            "dataset": "WRF",
                            "x": "time",
                            "var": "Temperatura",
                        }
                    ],
                },
            },
        }
        model = ControlFile.model_validate(cfg)
        assert "C" in model.plots
