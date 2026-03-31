from abc import ABC, abstractmethod
from pathlib import Path
import xarray as xr
from typing import Dict, Any


class Reader(ABC):
    """Reader abstract class.

    Implements interface and common logic for readers.
    """

    registry: dict[str, type["Reader"]] = {}
    type_aliases: list[str] = list()
    topology: str

    # Allows for self registering, and alias registering, for then looking up the right Data Class.
    def __init_subclass__(cls, **kwargs):
        """__init_subclass__ This Dunder method is being used to dinamically register all inheriting classes from Reader, this helps with Reader creation."""
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
        """get_reader_subclass Method for getting a class object from a string, centralizes the lookup operation for further development of smart lookup.

        Parameters
        ----------
        name : str
            String to lookup in reader class registry.

        Returns
        -------
        type
            Class object of adequate reader subclass.
        """
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
        """check_reader_class Method for checking if a string correlates to a reader subclass, meant to have the same lookup mechanism as get_reader_class

        Parameters
        ----------
        type : str
            String to lookup in reader class registry.

        Returns
        -------
        bool
            Boolean representing whether the type string corresponds to any reader subclass.
        """
        return (topology.lower() in cls.registry) and (
            reader.lower() in cls.registry[topology.lower()]
        )

    @staticmethod
    @abstractmethod
    def open_mfdataset(
        files: Path | list[Path], vars: Dict[str, Any] = None, **kwargs
    ) -> xr.Dataset:
        """open_mfdataset abstract main method of every reader. Reads files from a set of paths, managing the required arguments.


        Parameters
        ----------
        files : Path | list[Path]
            _description_
        vars : Dict[str, Any], optional
            _description_, by default None

        Returns
        -------
        xr.Dataset
            _description_
        """
        pass
