from ClimateGraph.data import Data
from ClimateGraph.plot import Plot
from ClimateGraph.utils.parser import Parser

from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)


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

    def set_analysis_data(self, analysis: dict = None):
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

    def run(self, control_path: Path):
        """run Run the ClimateGraph routine.

        Parameters
        ----------
        control_path : Path
            Path of the configuration file for the ClimateGraph run.
        """
        self.analysis, self.data, self.plots, self.domains = self.read_control(
            control_path
        )

        self.set_analysis_data()
        # if self.eager : self.load_data()
        self.plot()
        # self.stats() TODO: add a module for stats

        self.data, self.plots, self.domains = None, None, None
