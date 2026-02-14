import logging
from . import plots
logging.basicConfig(level=logging.INFO) #TODO: make this settable from yaml file.

class Plot:
    plot_functions = plots.AVAILABLE_PLOTS
    def __init__(self, name, type, data, **kwargs):
        self.name = name
        self.type = type
        self.data = data if isinstance(data, list) else [data]
        
        # self.domains = domains TODO: when i add domains
        self.kwargs = kwargs
        self.done = False

    @property
    def type(self):
        return self.type

    @type.setter
    def type(self, type):
        self.type = type
        self.plot_func = Plot.plot_functions.get(type)

    def plot(self):
        if self.done:
            logging.debug(f"Plot {self.name} was already created.")
            return self.figure
        logging.info(f"Plotting: {self.type} of {[data.name for data in self.datas]}.")
        # TODO: find the plot functions and give the kwargs correctly
        return self.figure