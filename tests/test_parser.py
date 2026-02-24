import pytest
import yaml
from pathlib import Path
from ClimateGraph.utils.parser import Parser
from ClimateGraph.utils.control_model import ControlFile
from ClimateGraph import Data, Plot

SAMPLE_YAML = """
analysis:
  output_path: ./test_data/results
  debug: True

data: 
  WRF_D02: 
    path: ./test_data/wrf-*
    topology: RegularGrid 
    reader: wrf 
    vars:  
      Temperatura:
        name: T2 
        unit: kelvin 
      Presion: 
        name: PSFC 
        unit: pascal 
  DMC: 
    path: ./test_data/dmc-2010-2019.nc
    topology: PointSurface 
    reader: dmc
    vars:
      Temperatura:
        name: temperatura 
        unit: degC 
      Presion: 
        name: presionEstacion 
        unit: hectopascal 

plots: 
  Timeseries: 
    type: timeseries
    time_interval: 1/1/2019 - 28/2/2019
    timestep: h
    base: DMC 
    other_data: WRF_D02 
    vars: [Temperatura, Presion] 
"""


def test_config_model_parsing():
    data = yaml.safe_load(SAMPLE_YAML)
    config = ControlFile.model_validate(data)

    assert config.analysis.output_path.exists()
    assert config.analysis.debug == True
    assert config.data["WRF_D02"].topology == "RegularGrid"
    assert config.data["WRF_D02"].reader == "wrf"
    assert config.data["WRF_D02"].vars["Temperatura"].name == "T2"
    assert (
        len(config.data["DMC"].path) > 0
    )
    assert (
        config.data["DMC"].path[0].exists()
    )
    assert config.plots["Timeseries"].type == "timeseries"
    assert "Temperatura" in config.plots["Timeseries"].vars


def test_input_reader_yaml(tmp_path):
    d = tmp_path / "control"
    d.mkdir()
    f = d / "test.yaml"
    f.write_text(SAMPLE_YAML)

    analysis, data, plots = Parser.parse_control(f)
    assert isinstance(analysis, dict)
    for _, data_instance in data.items():
        assert isinstance(data_instance, Data)
    for _, plot_instance in plots.items():
        assert isinstance(plot_instance, Plot)

    assert analysis["debug"] == True


def test_input_reader_yml(tmp_path):
    d = tmp_path / "control"
    d.mkdir()
    f = d / "test.yml"
    f.write_text(SAMPLE_YAML)

    analysis, data, plots = Parser.parse_control(f)
    assert isinstance(analysis, dict)
    for _, data_instance in data.items():
        assert isinstance(data_instance, Data)
    for _, plot_instance in plots.items():
        assert isinstance(plot_instance, Plot)

    assert analysis["debug"] == True
