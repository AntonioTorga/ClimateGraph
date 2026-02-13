from abc import ABC, abstractmethod
from pathlib import Path
import xarray as xr


class Reader(ABC):
    @abstractmethod
    def open_mfdataset(
        files: list[Path] | Path, var_list: list[str] = None, **kwargs
    ) -> xr.Dataset:
        pass
