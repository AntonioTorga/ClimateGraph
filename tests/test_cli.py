import pytest
from typer.testing import CliRunner
from ClimateGraph.CLI import app
from pathlib import Path

runner = CliRunner()

SAMPLE_YAML = """
analysis:
  timestep: D
data:
  WRF_D02:
    files: "some_files"
    type: RegularGrid
    vars:
      Temperatura:
        name: T2
plots:
  plt1:
    type: spatial-overlay
    vars: ["Temperatura"]
"""

def test_run_command(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text(SAMPLE_YAML)

    result = runner.invoke(app, ["run", str(f)])
    print(result.stdout)
    assert result.exit_code == 0
    # Since AppKernel.run doesn't print anything yet, we just check exit code.

def test_run_command_nonexistent_file():
    result = runner.invoke(app, ["run", "nonexistent.yaml"])
    assert result.exit_code != 0
