from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Annotated, Union, List
import logging
from pathlib import Path

from ClimateGraph.data import Data

logging.basicConfig(level=logging.INFO)  # TODO: make this settable from yaml file.


class Domain(ABC):
    registry: dict[str, type["Domain"]] = dict()
    aliases: List[str] = list()
    config: type["BaseModel"] | None = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for name in cls.aliases:
            Domain.registry[name] = cls
        Domain.registry[cls.__name__.lower()] = cls

    @classmethod
    def build_config_union(cls) -> Annotated:
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
    ):
        domain_class = cls.get_domain_class(type)
        kwargs = domain_config.model_extra if domain_config.model_extra else {}

        return domain_class(
            name,
            domain_config=domain_config,
            **kwargs,
        )

    def __init__(self, name, domain_config, **kwargs):
        self.domain_config = domain_config

        self.name = name
        self.domain_kwargs = kwargs

    @classmethod
    def check_domain_class(cls, type: str):
        return type.lower() in cls.registry

    @classmethod
    def get_domain_class(cls, name: str):
        return cls.registry[name.lower()]

    @abstractmethod
    def apply(self, data: Data):
        pass
