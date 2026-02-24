from abc import ABC, abstractmethod
from pathlib import Path
import xarray as xr
from typing import Dict, Any


class Reader(ABC):
    registry: dict[str, type["Reader"]] = {}
    type_aliases: list[str] = list()
    topology: str

    # Allows for self registering, and alias registering, for then looking up the right Data Class.
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if not hasattr(cls, "topology"):
            raise TypeError(f"{cls.__name__} must define a 'topology' attribute.")

        # Create topology bucket if missing
        topology = cls.topology.lower()
        if topology not in Reader.registry:
            Reader.registry[topology] = {}

        # Register under class name
        Reader.registry[topology][cls.__name__.lower()] = cls

        # Register aliases
        for alias in getattr(cls, "type_aliases", []):
            Reader.registry[topology][alias.lower()] = cls

    @classmethod
    def get_reader_subclass(cls, type: str, sub_type: str):
        type = type.lower()
        sub_type = sub_type.lower()

        if type not in cls.registry:
            raise ValueError(
                f"No topology type named {type}. Please use one of the following: {list(cls.registry.keys())}"
            )
        try:
            reader_class = cls.registry[type][sub_type]
        except KeyError:
            raise ValueError(f"No reader {sub_type} for topology {type}")
        return reader_class

    @classmethod
    def check_reader_type(cls, type: str, sub_type: str):
        return (type in cls.registry) and (sub_type in cls.registry[type])

    @staticmethod
    @abstractmethod
    def open_mfdataset(
        files: Path | list[Path], vars: Dict[str, Any] = None, **kwargs
    ) -> xr.Dataset:
        pass
