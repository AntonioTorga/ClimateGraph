import logging
from abc import ABC, abstractmethod

import xarray as xr
from pydantic import BaseModel

from ClimateGraph.utils.registry import RegistryMixin

logging.basicConfig(level=logging.INFO)  # TODO: make this settable from yaml file.

# TODO: Change the use of BaseModel for actual attributes to improve modularization.


class Domain(RegistryMixin, ABC):
    """The Domain abstract class.

    A class that abstracts the domain definition and interface.
    This class contains and implements attributes and methods common to all the domain subclasses.
    """

    registry: dict[str, type["Domain"]] = dict()
    aliases: list[str] = list()
    config: type["BaseModel"] | None = None

    @classmethod
    def create(
        cls,
        name: str,
        type: str,
        domain_config: BaseModel,
    ) -> "Domain":
        """create Creation of a Domain object with the adequate Domain subclass. Meant to be applied over xr.Datasets or xr.DataArray

        Parameters
        ----------
        name : str
            Name of the object, used for reference inside ClimateGraph execution.
        type : str
            Type of Domain, used for lookup in the Domain registry.
        domain_config : BaseModel
            BaseModel object of the corresponding config as a Pydantic model. Used as arguments for the actual domain handling.

        Returns
        -------
        Domain
            Domain object with the config, ready to be applied.
        """

        domain_class = cls.get_domain_class(type)
        kwargs = domain_config.model_extra if domain_config.model_extra else {}

        return domain_class(
            name,
            domain_config=domain_config,
            **kwargs,
        )

    def __init__(self, name: str, domain_config: BaseModel, **kwargs):
        """__init__ Domain initialization dunder method.

        Parameters
        ----------
        name : str
            Name of the object, used for reference inside ClimateGraph execution.
        domain_config : BaseModel
            BaseModel object of the corresponding config as a Pydantic model. Used as arguments for the actual domain handling.
        """
        self.domain_config = domain_config

        self.name = name
        self.domain_kwargs = kwargs

    @classmethod
    def check_domain_class(cls, type: str) -> bool:
        return cls.check_class(type)

    @classmethod
    def get_domain_class(cls, name: str):
        return cls.get_class(name)

    @abstractmethod
    def apply(self, data: xr.Dataset | xr.DataArray) -> xr.Dataset | xr.DataArray:
        """apply Abstract method meant for centralizing domain application logic.

        Parameters
        ----------
        data : xr.Dataset | xr.DataArray
            Xarray Dataset or DataArray into which the domain will be applied.

        Returns
        -------
        xr.Dataset|xr.DataArray
            Dataset with the domain applied. If the domain didn't apply to the data then the original will be returned.
        """
        pass
