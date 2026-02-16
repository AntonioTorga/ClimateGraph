from abc import ABC, abstractmethod
from pathlib import Path
import xarray as xr
from typing import Dict, Any


class Reader(ABC):
    registry: dict[str, type["Reader"]] = {}
    type_aliases: list[str] = list()

    # Allows for self registering, and alias registering, for then looking up the right Data Class.
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Reader.registry[cls.__name__.lower()] = cls

        for alias in getattr(cls, "type_aliases", []):
            Reader.registry[alias.lower()] = cls

    @classmethod
    def get_reader_subclass(cls, name: str):
        _name = name.lower()
        try:
            reader_class = cls.registry[_name]
        except KeyError:
            raise ValueError(
                f"No type named {name} recognized. Options are {cls.registry.keys()} (case insensitive)."
            )
        return reader_class

    @staticmethod
    @abstractmethod
    def open_mfdataset(
        files: Path | list[Path], vars: Dict[str, Any] = None, **kwargs
    ) -> xr.Dataset:
        pass
