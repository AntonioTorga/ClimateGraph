import pytest
from typer.testing import CliRunner
from ClimateGraph.cli import app
from pathlib import Path

runner = CliRunner()

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
    radius_of_influence: 10000
    base: DMC 
    other_data: WRF_D02 
    vars: [Temperatura, Presion] 
"""


def test_run_command(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text(SAMPLE_YAML)

    result = runner.invoke(app, ["run", str(f)])
    print(result.stdout)
    assert result.exit_code == 0


def test_run_command_nonexistent_file():
    result = runner.invoke(app, ["run", "nonexistent.yaml"])
    assert result.exit_code != 0
