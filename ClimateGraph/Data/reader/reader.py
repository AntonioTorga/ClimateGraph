from abc import ABC, abstractmethod
from pathlib import Path
import xarray as xr


class Reader(ABC):
    registry: dict[str, type["Reader"]] = {}
    type_aliases: list[str] = list()

    # Allows for self registering, and alias registering, for then looking up the right Data Class.
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Reader.registry[cls.__name__.lower()] = cls

        for alias in getattr(cls, "type_aliases", []):
            Reader.registry[alias.lower()] = cls
        print(f"Registry: \n{Reader.registry}")

    @abstractmethod
    @staticmethod
    def open_mfdataset(
        files: list[Path] | Path, var_list: list[str] = None, **kwargs
    ) -> xr.Dataset:
        pass

    @abstractmethod
    def postprocessing():
        pass
