from Data.Data import Data

from pathlib import Path


class AppKernel:
    def __init__(self):
        self.output_path = None
        self.control_path = None

        self.data = dict()
        self.plots = dict()
        # self.domains = dict() #TODO: replace placeholder with actual domain handling

    def run(self, control_path: Path):
        self.control_path = control_path
