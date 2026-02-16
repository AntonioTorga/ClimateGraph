import pytest
from pathlib import Path
import yaml
from ClimateGraph.utils.parser import Parser


@pytest.fixture
def config_file(tmp_path):
    config = {
        "analysis": {
            "timestep": "D",
            "start": "20/1/2001",
            "end": "30/1/2001",
            "results_path": str(tmp_path / "results"),
        },
        "data": {
            "WRF_D02": {
                "files": str(tmp_path / "wrf-d02-20*.nc"),
                "type": "RegularGrid",
                "subtype": "wrf",
            }
        },
        "plots": {
            "plt1": {
                "type": "spatial-overlay",
                "over": "DMC",
                "under": "WRF_D02",
                "vars": ["Temperatura"],
            }
        },
    }
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path


def test_parse_control(config_file):
    analysis, data, plots = Parser.parse_control(config_file, check_structure=True)

    assert analysis["timestep"] == "D"
    assert "WRF_D02" in data
    assert "plt1" in plots

    # Check if correct classes were instantiated (using strings for comparison if needed, or real classes)
    from ClimateGraph.data import RegularGrid
    from ClimateGraph.plot import Plot

    assert isinstance(data["WRF_D02"], RegularGrid)
    assert isinstance(plots["plt1"], Plot)
    assert plots["plt1"].kwargs["over"] == "DMC"
