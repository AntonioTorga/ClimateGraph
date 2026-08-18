from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ClimateGraph.utils.registry import RegistryMixin

if TYPE_CHECKING:
    from ClimateGraph.data.data import Data


class Domain(RegistryMixin, ABC):
    """The Domain abstract class.

    A class that abstracts the domain definition and interface.
    This class contains and implements attributes and methods common to all the domain subclasses.

    A domain application is a two-step template: an optional spatial *resample*
    onto another dataset's geometry (``resample_to`` in the config), followed by
    the subclass's own *filter* step (``_filter``). This lets a single domain
    express "this data, on that geometry, for this subset".
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
        target_data: "Data | None" = None,
    ) -> "Domain":
        """create Creation of a Domain object with the adequate Domain subclass. Applied over Data objects.

        Parameters
        ----------
        name : str
            Name of the object, used for reference inside ClimateGraph execution.
        type : str
            Type of Domain, used for lookup in the Domain registry.
        domain_config : BaseModel
            BaseModel object of the corresponding config as a Pydantic model. Used as arguments for the actual domain handling.
        target_data : Data | None, optional
            Resolved target dataset for the optional resample pre-step. The parser
            resolves ``domain_config.resample_to`` (a dataset name) into the actual
            ``Data`` object and passes it here. ``None`` when the domain does no
            resampling. By default None.

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
            target_data=target_data,
            **kwargs,
        )

    def __init__(
        self,
        name: str,
        domain_config: BaseModel,
        target_data: "Data | None" = None,
        **kwargs,
    ):
        """__init__ Domain initialization dunder method.

        Parameters
        ----------
        name : str
            Name of the object, used for reference inside ClimateGraph execution.
        domain_config : BaseModel
            BaseModel object of the corresponding config as a Pydantic model. Used as arguments for the actual domain handling.
        target_data : Data | None, optional
            Resolved target dataset for the optional resample pre-step, or None
            when the domain does no resampling. By default None.
        """
        self.domain_config = domain_config

        self.name = name
        self.domain_kwargs = kwargs
        self._resample_target = target_data

    @classmethod
    def check_domain_class(cls, type: str) -> bool:
        return cls.check_class(type)

    @classmethod
    def get_domain_class(cls, name: str):
        return cls.get_class(name)

    def apply(self, data: "Data") -> "Data":
        """apply Two-step template: optional resample pre-step, then the filter step.

        Parameters
        ----------
        data : Data
            Data object into which the domain will be applied.

        Returns
        -------
        Data
            Data object with the domain applied. When ``resample_to`` is set the
            result carries the target's topology/geometry (and the source's identity);
            otherwise the topology is unchanged.
        """
        if self._resample_target is not None:
            data = self._resample(data)
        return self._filter(data)

    def _resample(self, data: "Data") -> "Data":
        """_resample Reproject ``data`` onto the resample target's geometry.

        ``resample_vars`` is purely spatial, so the reprojected result keeps
        ``data``'s own time axis and inherits the target's spatial coords (site /
        region / lat / lon). It memoizes on the source, so several domains sharing a
        ``resample_to`` target (a ``one_for_each`` fan-out, or many hand-written
        domains onto one obs network) pay the projection cost once — the 2nd..Nth
        ``_resample`` here hit that cache. The returned value is a cheap
        target-topology wrapper wearing the SOURCE's identity (name + vars).

        Parameters
        ----------
        data : Data
            Source data to reproject.

        Returns
        -------
        Data
            The source data on the target's topology.
        """
        if data is self._resample_target:
            return data
        vars_list = list(data.obj.data_vars)
        resampled_ds = self._resample_target.resample_vars(
            data,
            vars_list,
            radius_of_influence=self.domain_config.radius_of_influence,
            engine=self.domain_config.engine,
            engine_kwargs=self.domain_config.engine_kwargs,
        )
        clean_ds = resampled_ds.rename({f"{v}__{data.name}": v for v in vars_list})
        result = self._resample_target.copy()
        result.obj = clean_ds
        result.name = data.name
        result._vars = data.vars
        return result

    @abstractmethod
    def _filter(self, data: "Data") -> "Data":
        """_filter Subclass hook: filter ``data`` (already resampled if requested).

        Parameters
        ----------
        data : Data
            Data object to filter.

        Returns
        -------
        Data
            Filtered Data object. If the filter doesn't apply, the original is returned.
        """
        pass
