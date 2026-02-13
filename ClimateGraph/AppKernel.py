from .Utils.InputReader import InputReader


class AppKernel:
    @staticmethod
    def run(file):
        input_data = InputReader.read(file)

        figures = input_data.get_figures()
        data = input_data.get_data()
