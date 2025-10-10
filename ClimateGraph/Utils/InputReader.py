from pathlib import Path
from abc import abstractmethod
import json
import yaml


class InputReader:
    @staticmethod
    def read(file: Path):
        if file.suffix == ".json":
            data = JsonReader.read(file)
        elif file.suffix == ".yaml":
            pass
        else:
            raise IOError(f"File type {file.suffix} isn't handled.")

        InputReader.check_input_data(data)

        return data

    def check_input_data(data):
        pass  # TODO: define data structure


class Reader:
    @abstractmethod
    @staticmethod
    def read(file: Path):
        pass


class JsonReader(Reader):
    @staticmethod
    def read(file: Path):
        with open(file) as fp:
            data = json.load(fp)
        return data


class YamlReader(Reader):
    @staticmethod
    def read(file: Path):
        with open(file) as fp:
            data = yaml.load(fp)
        return data
