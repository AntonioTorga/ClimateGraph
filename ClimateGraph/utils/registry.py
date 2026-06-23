from typing import Annotated, ClassVar, Union

from pydantic import BaseModel, Field


class RegistryMixin:
    """Mixin that provides a self-registering class registry.

    Each root ABC that inherits this mixin must declare its own:
        registry: ClassVar[dict[str, type]] = {}

    Concrete subclasses are registered automatically via __init_subclass__
    under their lowercased class name and any names listed in their ``aliases``
    class variable.  Only aliases declared directly on the subclass are
    registered (not inherited ones), matching the Reader convention.

    The mixin intentionally does NOT define ``registry`` itself — each root ABC
    owns a separate dict so their namespaces never collide.
    """

    aliases: ClassVar[list[str]] = []
    config: ClassVar[type[BaseModel] | None] = None

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        # Walk the MRO (skipping cls itself and RegistryMixin) to find the first
        # ancestor that declares its own ``registry`` dict.  That ancestor is the
        # root ABC for this family and owns the shared registry.
        owner = None
        for ancestor in cls.__mro__[1:]:
            if ancestor is RegistryMixin:
                continue
            if "registry" in ancestor.__dict__:
                owner = ancestor
                break

        if owner is None:
            return

        owner.registry[cls.__name__.lower()] = cls
        for alias in cls.__dict__.get("aliases", []):
            owner.registry[alias.lower()] = cls

    @classmethod
    def get_class(cls, name: str) -> type:
        """Look up a registered subclass by name (case-insensitive)."""
        try:
            return cls.registry[name.lower()]
        except KeyError as err:
            raise ValueError(
                f"No {cls.__name__} named '{name}'. "
                f"Options: {list(cls.registry)} (case-insensitive)."
            ) from err

    @classmethod
    def check_class(cls, name: str) -> bool:
        """Return True if *name* maps to a registered subclass."""
        return name.lower() in cls.registry

    @classmethod
    def build_config_union(cls) -> Annotated:
        """Build a Pydantic discriminated-union over all registered configs.

        Only meaningful for ABCs whose subclasses carry a ``config`` class
        attribute (Plot, Domain).  ``Data`` never calls this.
        """
        configs = [
            c.config
            for c in cls.registry.values()
            if getattr(c, "config", None) is not None
        ]
        # Union[tuple(configs)] unpacks at runtime — do not let Ruff rewrite this;
        # the UP007 rewrite strips Union and breaks Pydantic's discriminator.
        return Annotated[Union[tuple(configs)], Field(discriminator="type")]  # noqa: UP007
