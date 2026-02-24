from pathlib import Path
from abc import abstractmethod
import json
import yaml

from ClimateGraph.data import Data
from ClimateGraph.reader import Reader
from ClimateGraph.plot import Plot
from ClimateGraph.utils.general_utils import manage_path, manage_crs
from ClimateGraph.utils.control_model import ControlFile

FILE_READERS = {".json": json.load, ".yaml": yaml.safe_load, ".yml": yaml.safe_load}


class Parser:
    @staticmethod
    def parse_control(control_path: Path):
        control_dict = Parser.read_control(control_path)

        try:
            valid = ControlFile.model_validate(control_dict)
        except Exception as e:
            raise ValueError(
                f"Control file doesn't meet the input structure. Check the pydantic model in control_model.py to meet the necessary requirements."
            )

        analysis = valid.analysis.model_dump()
        data = dict()
        plots = dict()

        for data_name, data_model in valid.data.items():
            _name = data_name
            _topology, _reader, _path, _vars, _crs = (
                data_model.topology,
                data_model.reader,
                data_model.path,
                data_model.vars,
                data_model.crs,
            )
            _vars = {var: var_model.model_dump() for var, var_model in _vars.items()}

            reader_kwargs = (
                data_model.model_extra
            )  # Everything other than the required arguments will pass onto the reader

            data_instance = Data.create(
                _name, _topology, _reader, _path, _vars, _crs, reader_kwargs
            )

            data[_name] = data_instance

        for plot_name, plot_model in valid.plots.items():
            _type = plot_model.type
            plot_instance = Plot.create(
                plot_name, _type, plot_model, data, output_path=analysis["output_path"]
            )
            plots[plot_name] = plot_instance

        return analysis, data, plots

    @staticmethod
    def read_control(control_path: Path):
        control_path = control_path.resolve()
        if not (control_path.exists() and control_path.is_file()):
            raise FileNotFoundError(f"File {control_path} not found.")
        if (reader := FILE_READERS.get(control_path.suffix)) is None:
            raise ValueError(f"File type {control_path.suffix} not supported.")

        with open(control_path, mode="r") as fp:
            control_dict = reader(fp)
        return control_dict
