from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Annotated, Union, List
import logging
from pathlib import Path

import xarray as xr

logging.basicConfig(level=logging.INFO)  # TODO: make this settable from yaml file.

# TODO: Change the use of BaseModel for actual attributes to improve modularization.


class Domain(ABC):
    """The Domain abstract class.

    A class that abstracts the domain definition and interface.
    This class contains and implements attributes and methods common to all the domain subclasses.
    """

    registry: dict[str, type["Domain"]] = dict()
    aliases: List[str] = list()
    config: type["BaseModel"] | None = None

    def __init_subclass__(cls, **kwargs):
        """__init_subclass__ This Dunder method is being used to dinamically register all inheriting classes from Domain, this helps with Domain creation."""
        super().__init_subclass__(**kwargs)
        for name in cls.aliases:
            Domain.registry[name] = cls
        Domain.registry[cls.__name__.lower()] = cls

    @classmethod
    def build_config_union(cls) -> Annotated:
        """build_config_union Build an Annotated Union object used for the Pydantic model.

        Returns
        -------
        Annotated
            Used for the Pydantic model, dicriminates by type used when creating the Domain objects.
        """
        configs = [
            cls_.config for cls_ in Domain.registry.values() if cls_.config is not None
        ]
        return Annotated[Union[tuple(configs)], Field(discriminator="type")]

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
        """check_domain_class Method for checking if a string correlates to a Domain subclass, meant to have the same lookup mechanism as get_domain_class

        Parameters
        ----------
        type : str
            String to lookup in Domain class registry.

        Returns
        -------
        bool
            Boolean representing whether the type string corresponds to any Domain subclass.
        """
        return type.lower() in cls.registry

    @classmethod
    def get_domain_class(cls, name: str):
        """get_domain_class Method for getting a class object from a string, centralizes the lookup operation for further development of smart lookup.

        Parameters
        ----------
        name : str
            String to lookup in Domain class registry.

        Returns
        -------
        type
            Class object of adequate domain subclass.
        """
        return cls.registry[name.lower()]

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
