from pathlib import Path
from abc import abstractmethod
import json
import yaml
from .Models import ConfigModel


class InputReader:
    @staticmethod
    def read(file: Path):
        if file.suffix == ".json":
            data = JsonReader.read(file)
        elif file.suffix in [".yaml", ".yml"]:
            data = YamlReader.read(file)
        else:
            raise IOError(f"File type {file.suffix} isn't handled.")

        return ConfigModel.model_validate(data)


class Reader:
    @staticmethod
    @abstractmethod
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
            data = yaml.safe_load(fp)
        return data
