from ClimateGraph.data import Data
from ClimateGraph.plot import Plot
from ClimateGraph.utils import Parser

from pathlib import Path
import logging
logging.basicConfig(level=logging.INFO)

class AppKernel:
    def __init__(self):
        self.output_path = None
        self.analysis = None
        self.data = dict[str:Data]  # name : Data
        self.plots = dict[str:Plot]  # name : Plot

        self.debug = None
        self.output_path = None
        self.timestep = None
        self.start = None
        self.end = None
        
        # self.domains = dict() #TODO: replace placeholder with actual domain handling

    def read_control(self, control_path: Path):
        analysis, data, plots,= Parser.parse_control(self.control_path)
        return analysis, data, plots

    def load_data(self):
        for name, data_obj in self.data.items():
            logging.info(f"Loading '{name}' dataset.")
            data_obj.load_obj()

    def plot(self):
        for name, plot_obj in self.plots.items():
            logging.info(f"Plotting '{name}'.")
            plot_obj.plot()

    def set_analysis_data(self):
        self.debug = self.analysis.get("debug")
        self.output_path = self.analysis.get("output_path")
        self.start = self.analysis.get("start")
        self.end = self.analysis.get("end")
        self.timestep = self.analysis.get("timestep")

    def run(self, control_path: Path):
        self.analysis, self.data, self.plots= self.read_control(control_path)
        
        self.set_analysis_data()
        self.load_data()
        # self.create_domains() TODO: when i add domains
        self.plot()
        # self.stats() TODO: add a module for stats

        self.data, self.plots, self.collections = dict(), dict(), dict()
