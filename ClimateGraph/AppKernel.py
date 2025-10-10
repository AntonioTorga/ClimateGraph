from .Utils.InputReader import InputReader


class AppKernel:
    @staticmethod
    def run(file):
        input_data = InputReader.read(file)

        figures = input_data.get_figures()
        data = input_data.get_data()

        # TODO: Define if this function should receive the files and read them or receive just
        # an instance of the definition file
