import pytest
from pathlib import Path
import yaml
from ClimateGraph.utils.parser import Parser


@pytest.fixture
def config_file(tmp_path):
    config = {
        "analysis": {"output_path": str(tmp_path / "results"), "debug": True},
        "data": {
            "WRF_D02": {
                "path": "./test_data/wrf-2019-*.nc",
                "topology": "RegularGrid",
                "reader": "wrf",
                "vars": {"Temperatura": {"name": "T2", "unit": "kelvin"}},
            }
        },
        "plots": {
            "plt1": {
                "type": "timeseries",
                "base": "DMC",
                "other_data": "WRF_D02",
                "vars": "Temperatura",
                "radius_of_influence": 10000,
            }
        },
    }
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path


def test_parse_control(config_file):
    analysis, data, plts = Parser.parse_control(config_file)

    assert analysis["debug"] == True
    assert "WRF_D02" in data
    assert "plt1" in plts

    # Check if correct classes were instantiated (using strings for comparison if needed, or real classes)
    from ClimateGraph.data import RegularGrid
    from ClimateGraph.plot.plots import Timeseries

    assert isinstance(data["WRF_D02"], RegularGrid)
    assert isinstance(plts["plt1"], Timeseries)
    assert plts["plt1"].plot_config.base == "DMC"
