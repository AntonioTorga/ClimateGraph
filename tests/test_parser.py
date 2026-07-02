import pytest
import yaml

from ClimateGraph import Data, Plot
from ClimateGraph.domain.domains import AttributeConfig
from ClimateGraph.utils.control_model import ControlFile
from ClimateGraph.utils.parser import Parser, _expand_domains

SAMPLE_YAML = """
analysis:
  output_path: ./test_data/results
  debug: True

data:
  WRF_D02:
    path: ./test_data/data/wrf-*
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
    path: ./test_data/data/dmc-2010-2019.nc
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
    time: 1/1/2019 - 28/2/2019
    timestep: h
    base: DMC
    other_data: WRF_D02
    vars: [Temperatura, Presion]
    radius_of_influence: 10000

"""


def test_config_model_parsing():
    data = yaml.safe_load(SAMPLE_YAML)
    config = ControlFile.model_validate(data)

    assert config.analysis.output_path.exists()
    assert config.analysis.debug is True
    assert config.data["WRF_D02"].topology == "RegularGrid"
    assert config.data["WRF_D02"].reader == "wrf"
    assert config.data["WRF_D02"].vars["Temperatura"].name == "T2"
    assert len(config.data["DMC"].path) > 0
    assert config.data["DMC"].path[0].exists()
    assert config.plots["Timeseries"].type == "timeseries"
    assert "Temperatura" in config.plots["Timeseries"].vars


def test_input_reader_yaml(tmp_path):
    d = tmp_path / "control"
    d.mkdir()
    f = d / "test.yaml"
    f.write_text(SAMPLE_YAML)

    analysis, data, plots, _domains = Parser.parse_control(f)
    assert isinstance(analysis, dict)
    for _, data_instance in data.items():
        assert isinstance(data_instance, Data)
    for _, plot_instance in plots.items():
        assert isinstance(plot_instance, Plot)

    assert analysis["debug"] is True


def test_input_reader_yml(tmp_path):
    d = tmp_path / "control"
    d.mkdir()
    f = d / "test.yml"
    f.write_text(SAMPLE_YAML)

    analysis, data, plots, _domains = Parser.parse_control(f)
    assert isinstance(analysis, dict)
    for _, data_instance in data.items():
        assert isinstance(data_instance, Data)
    for _, plot_instance in plots.items():
        assert isinstance(plot_instance, Plot)

    assert analysis["debug"] is True


class TestExpandDomains:
    def test_passthrough_when_one_for_each_false(self):
        models = {
            "station": AttributeConfig(
                type="attr", field_name="station_id", field_value="STA01"
            )
        }
        expanded, rewrite_map = _expand_domains(models)
        assert expanded == models
        assert rewrite_map == {}

    def test_expands_list_into_one_domain_per_value(self):
        models = {
            "station": AttributeConfig(
                type="attr",
                field_name="station_id",
                field_value=["STA01", "STA02", "STA03"],
                one_for_each=True,
            )
        }
        expanded, rewrite_map = _expand_domains(models)
        assert set(expanded) == {"station__STA01", "station__STA02", "station__STA03"}
        for name, value in zip(
            ["station__STA01", "station__STA02", "station__STA03"],
            ["STA01", "STA02", "STA03"],
            strict=True,
        ):
            assert expanded[name].field_value == value
            assert expanded[name].one_for_each is False
        assert rewrite_map == {
            "station": ["station__STA01", "station__STA02", "station__STA03"]
        }

    def test_non_list_field_value_with_one_for_each_is_noop(self):
        models = {
            "station": AttributeConfig(
                type="attr",
                field_name="station_id",
                field_value="STA01",
                one_for_each=True,
            )
        }
        expanded, rewrite_map = _expand_domains(models)
        assert expanded == models
        assert rewrite_map == {}

    def test_mixed_expanded_and_passthrough_domains(self):
        models = {
            "station": AttributeConfig(
                type="attr",
                field_name="station_id",
                field_value=["STA01", "STA02"],
                one_for_each=True,
            ),
            "santiago": AttributeConfig(
                type="attr", field_name="region", field_value=13
            ),
        }
        expanded, rewrite_map = _expand_domains(models)
        assert set(expanded) == {"station__STA01", "station__STA02", "santiago"}
        assert rewrite_map == {"station": ["station__STA01", "station__STA02"]}


@pytest.mark.slow
class TestParseControlDomainExpansion:
    def test_plot_domains_resolved_to_expanded_names(self, tmp_path):
        yaml_with_domains = (
            SAMPLE_YAML
            + """
domains:
  station:
    type: attr
    field_name: codigoNacional
    field_value: [330020, 330021]
    one_for_each: true
"""
        )
        # Reference the un-expanded domain name from the plot block.
        yaml_with_domains = yaml_with_domains.replace(
            "    vars: [Temperatura, Presion]\n",
            "    vars: [Temperatura, Presion]\n    domains: [station]\n",
        )

        f = tmp_path / "control.yaml"
        f.write_text(yaml_with_domains)

        _analysis, _data, plots, domains = Parser.parse_control(f)

        assert set(domains) == {"station__330020", "station__330021"}
        assert plots["Timeseries"].plot_config.domains == [
            "station__330020",
            "station__330021",
        ]
