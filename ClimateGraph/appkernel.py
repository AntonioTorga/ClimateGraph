from data import Data, Reader, Collection
from plot import Plot
from utils import Parser
from pathlib import Path


class AppKernel:
    def __init__(self, output_path: Path):
        self.output_path = None
        self.analysis = None
        self.data = dict[str:Data]  # name : Data
        self.plots = dict[str:Plot]  # name : Plot
        # self.domains = dict() #TODO: replace placeholder with actual domain handling

    def read_control(self):
        analysis, data, plots,= Parser.parse_control(self.control_path)
        return analysis, data, plots

    def load_data(self):
        for name, data in self.data.items():
            print(f"Loading '{name}' dataset.")
            data.load_obj()

    def plot(self):
        for plot in self.plots.items():
            plot.plot()

    def creating_collections(self):
        for collection in self.collections:
            collection.gather(self.data)

    def run(self, control_path: Path):
        self.analysis, self.data, self.plots= self.read_control(control_path)

        self.load_data()
        # self.create_domains() TODO: when i add domains
        self.plot()
        # self.stats() TODO: add a module for stats

        self.data, self.plots, self.collections = dict(), dict(), dict()
