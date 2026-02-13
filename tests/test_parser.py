import pytest
import yaml
from pathlib import Path
from ClimateGraph.Utils.InputReader import InputReader
from ClimateGraph.Utils.Models import ConfigModel

SAMPLE_YAML = """
analysis:
  timestep: D
  start: 20/1/2001
  end: 30/1/2001
  results_path: /home/ato/results

data:
  WRF_D02:
    files: "/home/atorga/Melodies-Proyecto-MMA/Encargo-Nicolas/data/wrf-2/wrf-d02-20*.nc"
    type: RegularGrid
    subtype: wrf
    vars:
      Temperatura:
        name: T2
        unit: "kelvin"
      Presion:
        name: PSFC
        unit: "pascal"
  DMC:
    file: "/home/atorga/Melodies-Proyecto-MMA/Encargo-Nicolas/data/dmc-2/dmc-full.nc"
    type: PointSurface
    vars:
      Temperatura:
        name: temperatura
        unit: "degC"
      Presion:
        name: presionEstacion
        unit: "hectopascal"

plots:
  plt1:
    type: spatial-overlay
    over: "DMC"
    under: "WRF_D02"
    vars: ["Temperatura", "Presion"]
    title: ...
    extra_field: "some_value"
"""

def test_config_model_parsing():
    data = yaml.safe_load(SAMPLE_YAML)
    config = ConfigModel.model_validate(data)

    assert config.analysis.timestep == "D"
    assert config.analysis.start == "20/1/2001"
    assert config.data["WRF_D02"].type == "RegularGrid"
    assert config.data["WRF_D02"].subtype == "wrf"
    assert config.data["WRF_D02"].vars["Temperatura"].name == "T2"
    assert config.data["DMC"].file == "/home/atorga/Melodies-Proyecto-MMA/Encargo-Nicolas/data/dmc-2/dmc-full.nc"
    assert config.plots["plt1"].type == "spatial-overlay"
    assert config.plots["plt1"].over == "DMC"
    assert "Temperatura" in config.plots["plt1"].vars

    # Check extra fields
    assert config.plots["plt1"].model_extra["extra_field"] == "some_value"

def test_input_reader_yaml(tmp_path):
    d = tmp_path / "config"
    d.mkdir()
    f = d / "test.yaml"
    f.write_text(SAMPLE_YAML)

    config = InputReader.read(f)
    assert isinstance(config, ConfigModel)
    assert config.analysis.timestep == "D"

def test_input_reader_yml(tmp_path):
    d = tmp_path / "config"
    d.mkdir()
    f = d / "test.yml"
    f.write_text(SAMPLE_YAML)

    config = InputReader.read(f)
    assert isinstance(config, ConfigModel)
    assert config.analysis.timestep == "D"
