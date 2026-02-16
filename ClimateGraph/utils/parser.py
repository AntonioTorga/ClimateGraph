from pathlib import Path
from abc import abstractmethod
import json
import yaml

from ClimateGraph.data import Data
from ClimateGraph.reader import Reader
from ClimateGraph.plot import Plot

FILE_READERS = {".json": json.load, ".yaml": yaml.safe_load, ".yml": yaml.safe_load}


class Parser:
    @staticmethod
    def parse_control(
        control_path: Path, check_structure: bool = False
    ) -> dict[str:Data]:
        control_dict = Parser.read_control(control_path)

        if check_structure:
            try:
                control_dict.model_validate(control_dict)
            except Exception as e:
                print(e.errors())
                raise ValueError(
                    f"Control file doesn't meet the input structure. Check the pydantic model in control_model.py to meet the necessary requirements."
                )

        analysis = control_dict.get("analysis")

        data = dict()
        plots = dict()

        for data_name, data_block in control_dict["data"].items():
            _name = data_name
            _type, _subtype, _path = (
                data_block.pop("type", None),
                data_block.pop("subtype", None),
                data_block.pop("path", None),
            )
            # TODO: manage ccrs with get attr or get class from cartopy

            _vars = data_block.pop("vars", {})
            kwargs = data_block

            data_class = Data.get_data_subclass(_type)
            reader_class = Reader.get_reader_subclass(_subtype)

            data_instance = data_class(_name, _path, _vars, **kwargs)

            data[_name] = data_instance

        for plot_name, plot_block in control_dict["plots"].items():
            _type, _data = plot_block.pop("type"), plot_block.pop("data")
            kwargs = plot_block
            plot_instance = Plot(plot_name, _type, _data, **kwargs)
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
