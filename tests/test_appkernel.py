import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ClimateGraph.appkernel import AppKernel


@pytest.fixture
def stubbed_parser(monkeypatch, tmp_path):
    """Replace Parser.parse_control with a stub returning controllable values."""
    plot_mock = MagicMock()
    data_mock = MagicMock()
    analysis = {"debug": True, "output_path": tmp_path}
    data = {"d1": data_mock}
    plots = {"p1": plot_mock}
    domains = {}

    def fake_parse(_control_path):
        return analysis, data, plots, domains

    from ClimateGraph.appkernel import Parser

    monkeypatch.setattr(Parser, "parse_control", staticmethod(fake_parse))
    return analysis, data, plots, domains, plot_mock


class TestRun:
    def test_propagates_analysis(self, stubbed_parser, tmp_path):
        _analysis, _, _, _, _ = stubbed_parser
        kernel = AppKernel()
        kernel.run(tmp_path / "ignored.yaml")
        assert kernel.debug is True
        assert kernel.output_path == tmp_path

    def test_calls_plot_on_each(self, stubbed_parser, tmp_path):
        _, _, _, _, plot_mock = stubbed_parser
        kernel = AppKernel()
        kernel.run(tmp_path / "ignored.yaml")
        plot_mock.plot.assert_called_once()

    def test_clears_refs_after_run(self, stubbed_parser, tmp_path):
        kernel = AppKernel()
        kernel.run(tmp_path / "ignored.yaml")
        assert kernel.data is None
        assert kernel.plots is None
        assert kernel.domains is None


class TestSetAnalysisData:
    def test_defaults_when_keys_missing(self):
        kernel = AppKernel()
        kernel.set_analysis_data({})
        assert kernel.debug is False
        assert kernel.output_path == Path("./")

    def test_uses_self_analysis_when_arg_is_none(self):
        kernel = AppKernel()
        kernel.analysis = {"debug": True, "output_path": Path("/tmp/foo")}
        kernel.set_analysis_data()
        assert kernel.debug is True
        assert kernel.output_path == Path("/tmp/foo")


class TestConfigureLogging:
    def test_debug_true_raises_only_climategraph_logger(self):
        kernel = AppKernel()
        kernel.debug = True
        kernel._configure_logging()
        # Debug is scoped to the ClimateGraph package logger; root stays INFO so
        # third-party libraries (matplotlib, PIL) don't spray DEBUG.
        assert logging.getLogger("ClimateGraph").level == logging.DEBUG
        assert logging.getLogger().level == logging.INFO

    def test_debug_false_sets_info_level(self):
        kernel = AppKernel()
        kernel.debug = False
        kernel._configure_logging()
        assert logging.getLogger("ClimateGraph").level == logging.INFO
        assert logging.getLogger().level == logging.INFO


class TestDebugOverride:
    def test_override_true_wins_over_config_false(self, stubbed_parser, tmp_path):
        analysis, _, _, _, _ = stubbed_parser
        analysis["debug"] = False
        kernel = AppKernel()
        kernel.run(tmp_path / "ignored.yaml", debug_override=True)
        assert kernel.debug is True

    def test_override_false_keeps_config_true(self, stubbed_parser, tmp_path):
        analysis, _, _, _, _ = stubbed_parser
        analysis["debug"] = True
        kernel = AppKernel()
        kernel.run(tmp_path / "ignored.yaml", debug_override=False)
        assert kernel.debug is True

    def test_override_false_keeps_config_false(self, stubbed_parser, tmp_path):
        analysis, _, _, _, _ = stubbed_parser
        analysis["debug"] = False
        kernel = AppKernel()
        kernel.run(tmp_path / "ignored.yaml", debug_override=False)
        assert kernel.debug is False
