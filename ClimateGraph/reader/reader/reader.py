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
    def get_reader_subclass(cls, topology: str, reader: str):
        topology = topology.lower()
        reader = reader.lower()

        if topology not in cls.registry:
            raise ValueError(
                f"No topology type named {topology}. Please use one of the following: {list(cls.registry.keys())}"
            )
        try:
            reader_class = cls.registry[topology][reader]
        except KeyError:
            raise ValueError(f"No reader {reader} for topology {topology}")
        return reader_class

    @classmethod
    def check_reader_type(cls, topology: str, reader: str):
        return (topology.lower() in cls.registry) and (
            reader.lower() in cls.registry[topology.lower()]
        )

    @staticmethod
    @abstractmethod
    def open_mfdataset(
        files: Path | list[Path], vars: Dict[str, Any] = None, **kwargs
    ) -> xr.Dataset:
        pass
