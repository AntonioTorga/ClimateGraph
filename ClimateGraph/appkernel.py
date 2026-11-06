"""Execution and state management.

Connects the modules of the application to each other: holds the registries of
the objects the parser built, promotes the control file's ``analysis`` block to
run-scoped settings, and dispatches the jobs those objects describe.

The main loop lives in :meth:`AppKernel.run`. Plotting is the only job type
dispatched today; analysis jobs are the intended next one.
"""

import logging
import sys
from contextlib import contextmanager
from pathlib import Path

from ClimateGraph.utils.parser import Parser

log = logging.getLogger(__name__)

# ``module`` is the calling file's bare name, so the origin shows without the
# dotted path. The severity is already implied by which stream a record is on.
_PLAIN_FORMAT = "%(module)-14s %(message)s"
# Debug puts every record on one stream, so each needs its full origin.
_DEBUG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class AppKernel:
    """ClimateGraph execution and state manager. Orquestrates the other modules."""

    def __init__(self):
        """Create an empty kernel. Registries and settings are filled by :meth:`run`."""
        self.analysis = None
        self.data = None
        self.domains = None
        self.plots = None

        self.debug = None
        self.verbose = None
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

    def summary(self):
        """Report the size of the run before any file is opened.

        Every count comes from the parsed config, so this costs no IO. Paths
        are already glob-expanded by ``DataModel.val_file_path``, and
        ``Plot.expected_figures`` reads the fan-out off the plot config.
        """
        datasets, plots = self.data or {}, self.plots or {}
        width = max((len(n) for n in (*datasets, *plots)), default=0)

        log.info("Run summary")
        for name, dataset in datasets.items():
            paths = dataset.path if isinstance(dataset.path, list) else [dataset.path]
            log.info(
                "  data  %-*s  %4d files  %s via %s",
                width,
                name,
                len(paths),
                type(dataset).__name__,
                # The reader is held as a class, not an instance.
                getattr(dataset.reader, "__name__", dataset.reader),
            )
        if self.domains:
            log.info("  domains  %s", ", ".join(self.domains))

        total = 0
        for name, plot_obj in plots.items():
            figures = plot_obj.expected_figures()
            total += figures
            log.info(
                "  plot  %-*s  %4d figures  %s",
                width,
                name,
                figures,
                plot_obj.plot_config.type,
            )
        log.info("  total %d figures -> %s", total, self.output_path)

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
        self.verbose = analysis.get("verbose", False)
        self.output_path = analysis.get("output_path", Path("./"))
        self.workers = analysis.get("workers")

    def _configure_logging(self):
        """Route records to stdout or stderr by severity, and set verbosity.

        Three levels. ``normal`` reports what is being rendered; ``verbose``
        adds per-stage detail; ``debug`` additionally puts everything on one
        stream so a trace reads in order.

        Routine output goes to **stdout**. A scheduler that splits the streams
        (``#SBATCH -o out.log -e err.log``) then leaves the error file empty on
        a clean run, instead of filling it with INFO and reading as a failure.

        The only place in the codebase that calls ``logging.basicConfig``.
        ``force=True`` so this always wins regardless of import order, and so
        it can be called twice — once on the CLI flags before the control file
        is read, once more with the file's own settings.

        The root logger stays at INFO so third-party libraries (matplotlib,
        PIL, …) never spray DEBUG. Only the ``ClimateGraph`` package logger is
        raised; its records still reach the root handler, so our own trace
        shows while the noisy libraries stay quiet.
        """
        out = logging.StreamHandler(sys.stdout)
        handlers = [out]

        if self.debug:
            out.setLevel(logging.DEBUG)
            out.setFormatter(logging.Formatter(_DEBUG_FORMAT))
        else:
            # The split already says what a record is, so routine output needs
            # no prefix and only the stderr side is tagged.
            out.addFilter(lambda record: record.levelno < logging.WARNING)
            out.setFormatter(logging.Formatter(_PLAIN_FORMAT))
            err = logging.StreamHandler(sys.stderr)
            err.setLevel(logging.WARNING)
            err.setFormatter(logging.Formatter(f"%(levelname)s {_PLAIN_FORMAT}"))
            handlers.append(err)

        logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
        logging.getLogger("ClimateGraph").setLevel(
            logging.DEBUG if (self.debug or self.verbose) else logging.INFO
        )

    def run(
        self,
        control_path: Path,
        debug_override: bool = False,
        verbose_override: bool = False,
    ):
        """Run the ClimateGraph routine.

        Reads the control file, sets up the run-scoped settings, reports the
        size of the run, dispatches the plotting jobs, then clears the
        registries.

        Parameters
        ----------
        control_path : Path
            Path of the configuration file for the ClimateGraph run.
        debug_override : bool, optional
            CLI ``--debug`` flag. ORed with the control file's ``debug`` value:
            either source enables DEBUG, neither disables it. Default False.
        verbose_override : bool, optional
            CLI ``--verbose`` flag, ORed with the control file the same way.
        """
        # Configured twice: once on the CLI flags so parsing errors are covered
        # at the requested level, once more with the control file's own values.
        self.debug, self.verbose = debug_override, verbose_override
        self._configure_logging()

        self.analysis, self.data, self.plots, self.domains = self.read_control(
            control_path
        )

        self.set_analysis_data()
        self.debug = debug_override or self.debug
        self.verbose = verbose_override or self.verbose
        self._configure_logging()

        self.summary()
        # if self.eager : self.load_data()
        with self._dask_client():
            self.plot()
        # self.stats() TODO: add a module for stats

        self.data, self.plots, self.domains = None, None, None

    @contextmanager
    def _dask_client(self):
        """Yield a dask client, or ``None`` when no cluster was requested.

        One thread per worker: libnetcdf is not thread-safe, so reads serialise
        behind a global lock that is held per process. Threads therefore queue
        on it while processes read in parallel.

        Yields
        ------
        dask.distributed.Client or None
        """
        if not self.workers:
            yield None
            return
        from dask.distributed import Client, LocalCluster

        cluster = LocalCluster(n_workers=self.workers, threads_per_worker=1)
        client = Client(cluster)
        log.info(f"Dask Client started: {self.workers} workers x 1 thread.")
        try:
            yield client
        finally:
            client.close()
            cluster.close()
