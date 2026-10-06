"""Execution and state management.

Connects the modules of the application to each other: holds the registries of
the objects the parser built, promotes the control file's ``analysis`` block to
run-scoped settings, and dispatches the jobs those objects describe.

The main loop lives in :meth:`AppKernel.run`. Plotting is the only job type
dispatched today; analysis jobs are the intended next one.
"""

import logging
from contextlib import contextmanager
from pathlib import Path

from ClimateGraph.utils.parser import Parser

log = logging.getLogger(__name__)


class AppKernel:
    """ClimateGraph execution and state manager. Orquestrates the other modules."""

    def __init__(self):
        """Create an empty kernel. Registries and settings are filled by :meth:`run`."""
        self.analysis = None
        self.data = None
        self.domains = None
        self.plots = None

        self.debug = None
        self.output_path = None
        self.workers = None

    def read_control(self, control_path: Path):
        """Read and validate a control file through the :class:`~ClimateGraph.utils.parser.Parser`.

        Parameters
        ----------
        control_path : Path
            Pathlib path to a control file.

        Returns
        -------
        BaseModel, Dict[str, Data], Dict[str, Plot], Dict[str, Domain]
            All necessary data for running a ClimateGraph execution
        """
        analysis, data, plots, domains = Parser.parse_control(control_path)
        return analysis, data, plots, domains

    def load_data(self):
        """Eagerly load every registered dataset.

        Not called by :meth:`run`, which relies on :class:`~ClimateGraph.data.Data`
        loading lazily on first access instead.
        """
        for name, data_obj in self.data.items():
            log.info(f"Loading '{name}' dataset.")
            data_obj.load_obj()

    def plot(self):
        """Dispatch one plotting job per registered plot."""
        for name, plot_obj in self.plots.items():
            log.info(f"Plotting '{name}'.")
            plot_obj.plot()

    def set_analysis_data(self, analysis: dict | None = None):
        """Promote the control file's ``analysis`` block to kernel settings.

        Parameters
        ----------
        analysis : dict, optional
            Mapping holding ``output_path``, ``debug`` and ``workers``. Defaults
            to the block read from the control file.
        """
        if analysis is None:
            analysis = self.analysis

        self.debug = analysis.get("debug", False)
        self.output_path = analysis.get("output_path", Path("./"))
        self.workers = analysis.get("workers")

    def _configure_logging(self):
        """Scope ``--debug`` to ClimateGraph's own logger.

        The only place in the codebase that calls ``logging.basicConfig``.
        ``force=True`` so this always wins regardless of import order, even if
        some other library configured logging before this runs.

        The root logger stays at INFO so third-party libraries (matplotlib, PIL,
        …) never spray DEBUG. ``--debug`` only raises the ``ClimateGraph`` package
        logger to DEBUG; its records still reach the root handler (NOTSET, emits
        everything), so ClimateGraph's own operation traceback shows while the
        noisy libraries stay quiet.
        """
        logging.basicConfig(level=logging.INFO, force=True)
        logging.getLogger("ClimateGraph").setLevel(
            logging.DEBUG if self.debug else logging.INFO
        )

    def run(self, control_path: Path, debug_override: bool = False):
        """Run the ClimateGraph routine.

        Reads the control file, sets up the run-scoped settings, dispatches the
        plotting jobs, then clears the registries.

        Parameters
        ----------
        control_path : Path
            Path of the configuration file for the ClimateGraph run.
        debug_override : bool, optional
            CLI ``--debug`` flag. ORed with the control file's ``debug`` value:
            either source enables DEBUG, neither disables it. Default False.
        """
        self.analysis, self.data, self.plots, self.domains = self.read_control(
            control_path
        )

        self.set_analysis_data()
        self.debug = debug_override or self.debug
        self._configure_logging()
        # if self.eager : self.load_data()
        with self._dask_client():
            self.plot()
        # self.stats() TODO: add a module for stats

        self.data, self.plots, self.domains = None, None, None

    @contextmanager
    def _dask_client(self):
        """Yield a dask client, or ``None`` when no cluster was requested.

        Yields
        ------
        dask.distributed.Client or None
        """
        if not self.workers:
            yield None
            return
        from dask.distributed import Client, LocalCluster

        cluster = LocalCluster(n_workers=1, threads_per_worker=self.workers)
        client = Client(cluster)
        log.info(f"Dask Client started: 1 worker x {self.workers} threads.")
        try:
            yield client
        finally:
            client.close()
            cluster.close()
