"""Reader for CHIMERE model output."""

import logging

import xarray as xr

from ..reader import ReadSpec
from .default import DefaultRegularGridReader

log = logging.getLogger(__name__)


class Chimere(DefaultRegularGridReader):
    rename = {
        "nav_lat": "latitude",
        "nav_lon": "longitude",
        "time_counter": "time",
        "bottom_top": "z",
    }

    @classmethod
    def _postprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Shape CHIMERE output into the common grid layout."""
        return ds
