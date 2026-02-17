import logging
from . import plots

logging.basicConfig(level=logging.INFO)  # TODO: make this settable from yaml file.


class Plot:
    plot_functions = plots.AVAILABLE_PLOTS

    def __init__(self, name, type, **kwargs):
        self._type = None
        self._plot_func = None
        self.figure = None

        self.name = name
        self.type = type

        self.kwargs = kwargs
        self._done = False

    @classmethod
    def check_plot_type(cls, type: str):
        return type in cls.plot_functions

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, type):
        self._type = type
        self._plot_func = Plot.plot_functions.get(type)

    def plot(self):
        if self._done:
            logging.debug(f"Plot {self.name} was already created.")
            return self.figure
        logging.info(f"Plotting: {self.type} of {[data.name for data in self.datas]}.")
        self.plot_func()  # TODO: fill this with the parameters
        return self.figure
