from Data.Data import Data
from Utils.Parser import Parser
from pathlib import Path


class AppKernel:
    def __init__(self, output_path: Path):
        self.output_path = None

        self.datas = dict()  # name : Data
        self.plots = dict()  # name : Plot
        self.collections = dict()  # base_name : Collection
        # self.domains = dict() #TODO: replace placeholder with actual domain handling
        # self.stats = dict()

    def read_control(self):
        datas, plots = Parser.parse_control(self.control_path)
        return datas, plots

    def load_data(self):
        for name, data in self.datas.items():
            print(f"Loading '{name}' dataset.")
            data.load_obj()

    def plot(self):
        for plot in self.plots.items():
            plot.plot()

    def creating_collections(self):
        for collection in self.collections:
            collection.gather(self.datas)

    def run(self, control_path: Path):
        datas, plots = self.read_control(control_path)

        self.load_data()
        # self.create_domains() TODO: when i add domains
        self.creating_collections()
        self.plot()
        # self.stats() TODO: add a module for stats

        self.datas, self.plots, self.collections = dict(), dict(), dict()
