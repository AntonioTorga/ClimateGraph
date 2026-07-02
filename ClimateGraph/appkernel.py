import logging
from contextlib import contextmanager
from pathlib import Path

from ClimateGraph.utils.parser import Parser


class AppKernel:
    """ClimateGraph execution and state manager. Orquestrates the other modules."""

    def __init__(self):
        """__init__ AppKernel initialization dunder method"""
        self.output_path = None
        self.analysis = None
        self.data = None
        self.domains = None
        self.plots = None  # name : Plot

        self.debug = None
        self.output_path = None
        self.workers = None

    def read_control(self, control_path: Path):
        """read_control Uses the Parser from utils to read a control file.

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
        """load_data Load the data objects."""
        for name, data_obj in self.data.items():
            logging.info(f"Loading '{name}' dataset.")
            data_obj.load_obj()

    def plot(self):
        """plot Perform plots. Runs the plot method from the plot objects."""
        for name, plot_obj in self.plots.items():
            logging.info(f"Plotting '{name}'.")
            plot_obj.plot()

    def set_analysis_data(self, analysis: dict | None = None):
        """set_analysis_data Set analysis data in the AppKernel instance.

        Parameters
        ----------
        analysis : dict, optional
            Dictionary with debug and output_path mapping values, by default None
        """
        if analysis is None:
            analysis = self.analysis

        self.debug = analysis.get("debug", False)
        self.output_path = analysis.get("output_path", Path("./"))
        self.workers = analysis.get("workers")

    def _configure_logging(self):
        """_configure_logging Set the root logger level from self.debug.

        The only place in the codebase that calls ``logging.basicConfig``.
        ``force=True`` so this always wins regardless of import order, even if
        some other library configured logging before this runs.
        """
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(level=level, force=True)

    def run(self, control_path: Path, debug_override: bool = False):
        """run Run the ClimateGraph routine.

        Parameters
        ----------
        control_path : Path
            Path of the configuration file for the ClimateGraph run.
        debug_override : bool, optional
            CLI override for the control file's ``debug`` setting. ORed with
            the control file's value, so passing True always wins. By default False
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
        if not self.workers:
            yield None
            return
        from dask.distributed import Client, LocalCluster

        cluster = LocalCluster(n_workers=1, threads_per_worker=self.workers)
        client = Client(cluster)
        logging.info(f"Dask Client started: 1 worker x {self.workers} threads.")
        try:
            yield client
        finally:
            client.close()
            cluster.close()
