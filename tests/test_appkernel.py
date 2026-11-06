import logging
import subprocess
import sys
import textwrap
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


class TestLogStreams:
    """Routine output belongs on stdout.

    A scheduler splitting the streams (``-o out.log -e err.log``) used to get
    an empty out.log and an err.log full of INFO, so a clean run read as a
    failure.
    """

    SCRIPT = textwrap.dedent("""
        import logging
        from ClimateGraph.appkernel import AppKernel
        kernel = AppKernel()
        kernel.debug, kernel.verbose = {debug}, {verbose}
        kernel._configure_logging()
        log = logging.getLogger("ClimateGraph.probe")
        log.debug("D"); log.info("I"); log.warning("W"); log.error("E")
    """)

    def _streams(self, debug: bool, verbose: bool) -> tuple[list[str], list[str]]:
        """Run a probe in a subprocess, since basicConfig is process-global."""
        result = subprocess.run(
            [sys.executable, "-c", self.SCRIPT.format(debug=debug, verbose=verbose)],
            capture_output=True,
            text=True,
            check=True,
        )
        messages = lambda text: [  # noqa: E731
            line.split()[-1] for line in text.strip().splitlines() if line
        ]
        return messages(result.stdout), messages(result.stderr)

    def test_normal_puts_progress_on_stdout_and_problems_on_stderr(self):
        out, err = self._streams(debug=False, verbose=False)
        assert out == ["I"]
        assert err == ["W", "E"]

    def test_verbose_adds_detail_and_keeps_the_split(self):
        out, err = self._streams(debug=False, verbose=True)
        assert out == ["D", "I"]
        assert err == ["W", "E"]

    def test_debug_puts_everything_on_stdout(self):
        # One stream so a trace reads in order.
        out, err = self._streams(debug=True, verbose=False)
        assert out == ["D", "I", "W", "E"]
        assert err == []


class TestVerboseOverride:
    def test_override_true_wins_over_config_false(self, stubbed_parser, tmp_path):
        analysis, _, _, _, _ = stubbed_parser
        analysis["verbose"] = False
        kernel = AppKernel()
        kernel.run(tmp_path / "ignored.yaml", verbose_override=True)
        assert kernel.verbose is True

    def test_override_false_keeps_config_true(self, stubbed_parser, tmp_path):
        analysis, _, _, _, _ = stubbed_parser
        analysis["verbose"] = True
        kernel = AppKernel()
        kernel.run(tmp_path / "ignored.yaml", verbose_override=False)
        assert kernel.verbose is True

    def test_missing_from_config_defaults_false(self, stubbed_parser, tmp_path):
        kernel = AppKernel()
        kernel.run(tmp_path / "ignored.yaml")
        assert kernel.verbose is False


class TestSummary:
    def _loaded(self, stubbed_parser):
        """A kernel holding the stub registries, without running.

        ``run`` calls ``basicConfig(force=True)``, which replaces caplog's
        handler, so the summary is exercised on its own.
        """
        analysis, data, plots, domains, plot_mock = stubbed_parser
        kernel = AppKernel()
        kernel.analysis, kernel.data = analysis, data
        kernel.plots, kernel.domains = plots, domains
        kernel.set_analysis_data()
        return kernel, plot_mock

    def test_reports_counts_before_running(self, stubbed_parser, caplog):
        kernel, plot_mock = self._loaded(stubbed_parser)
        plot_mock.expected_figures.return_value = 4
        with caplog.at_level(logging.INFO, logger="ClimateGraph.appkernel"):
            kernel.summary()
        assert "Run summary" in caplog.text
        assert "total 4 figures" in caplog.text

    def test_summary_costs_no_io(self, stubbed_parser, caplog):
        # Counts come off the config; nothing may touch the data.
        kernel, _ = self._loaded(stubbed_parser)
        with caplog.at_level(logging.INFO, logger="ClimateGraph.appkernel"):
            kernel.summary()
        kernel.data["d1"].load_obj.assert_not_called()


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


class TestDaskClient:
    """``workers`` must buy worker processes, not threads.

    libnetcdf is not thread-safe, so xarray serialises reads behind a lock held
    per process. Threads queue on it and measure slower than no cluster at all;
    processes each hold their own and read in parallel.
    """

    @pytest.fixture
    def captured_cluster(self, monkeypatch):
        captured = {}

        class _FakeCluster:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def close(self):
                pass

        import dask.distributed

        monkeypatch.setattr(dask.distributed, "LocalCluster", _FakeCluster)
        monkeypatch.setattr(dask.distributed, "Client", lambda cluster: MagicMock())
        return captured

    def test_workers_become_processes(self, captured_cluster):
        kernel = AppKernel()
        kernel.workers = 8
        with kernel._dask_client() as client:
            assert client is not None
        assert captured_cluster["n_workers"] == 8
        assert captured_cluster["threads_per_worker"] == 1

    def test_no_workers_means_no_cluster(self, captured_cluster):
        kernel = AppKernel()
        kernel.workers = None
        with kernel._dask_client() as client:
            assert client is None
        assert captured_cluster == {}
