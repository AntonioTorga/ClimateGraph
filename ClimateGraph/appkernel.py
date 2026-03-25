from ClimateGraph.data import Data
from ClimateGraph.plot import Plot
from ClimateGraph.utils.parser import Parser

from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)


class AppKernel:
    def __init__(self):
        self.output_path = None
        self.analysis = None
        self.data = None
        self.domains = None
        self.plots = None # name : Plot

        self.debug = None
        self.output_path = None

        # self.domains = dict() #TODO: replace placeholder with actual domain handling

    def read_control(self, control_path: Path):
        (
            analysis,
            data,
            plots,
            domains
        ) = Parser.parse_control(control_path)
        return analysis, data, plots, domains

    def load_data(self):
        for name, data_obj in self.data.items():
            logging.info(f"Loading '{name}' dataset.")
            data_obj.load_obj()

    def plot(self):
        for name, plot_obj in self.plots.items():
            logging.info(f"Plotting '{name}'.")
            plot_obj.plot()

    def set_analysis_data(self, analysis: dict = None):
        if analysis is None:
            analysis = self.analysis

        self.debug = analysis.get("debug", False)
        self.output_path = analysis.get("output_path", Path("./"))

    def run(self, control_path: Path):
        self.analysis, self.data, self.plots = self.read_control(control_path)

        self.set_analysis_data()
        # if self.eager : self.load_data()
        self.plot()

        # self.stats() TODO: add a module for stats

        self.data, self.plots, self.domains = None, None, None
