class Plot:
    def __init__(self, type, datas, **kwargs):
        self.type = type
        self._reader = None
        self.datas = datas
        # self.domains = domains TODO: when i add domains
        self.kwargs = kwargs
        self.done = False

    @property
    def type(self):
        return self.type

    @type.setter
    def type(self):
        plot_functions = Plots.__all__

    def plot(self):
        print(f"Plotting: {self.type} of {[data.name for data in self.datas]}.")
